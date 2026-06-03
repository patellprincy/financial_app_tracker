package com.finsightai.presentation.upload

import android.app.Application
import android.net.Uri
import android.provider.OpenableColumns
import android.util.Log
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.viewModelScope
import com.finsightai.data.local.SessionManager
import com.finsightai.data.network.RetrofitClient
import com.finsightai.data.repository.StatementRepositoryImpl
import com.finsightai.domain.model.ExtractedTransaction
import com.finsightai.domain.model.SelectedFile
import com.finsightai.domain.model.StatementUploadResponse
import com.finsightai.domain.repository.StatementRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

// ── Supporting types ───────────────────────────────────────────────────────

/** Tracks a removed transaction alongside its original position for stable undo. */
data class RemovedTransaction(
    val transaction: ExtractedTransaction,
    val originalIndex: Int
)

/**
 * One-shot event that triggers the undo snackbar.
 * [id] is always unique (System.currentTimeMillis) so LaunchedEffect re-fires
 * on each removal even when the same transaction is removed twice.
 */
data class UndoEvent(
    val removed: RemovedTransaction,
    val id: Long
)

// ── Upload state machine ───────────────────────────────────────────────────

sealed interface UploadState {
    data object Idle : UploadState
    data object Uploading : UploadState
    data class Success(val response: StatementUploadResponse) : UploadState
    data class Error(val message: String) : UploadState
}

// ── Screen-level UI state ──────────────────────────────────────────────────

data class UploadUiState(
    val selectedFile: SelectedFile? = null,
    val uploadState: UploadState = UploadState.Idle,
    // Preview management — populated once uploadState becomes Success
    val visibleTransactions: List<ExtractedTransaction> = emptyList(),
    val removedTransactions: List<RemovedTransaction> = emptyList(),
    val totalExpense: Double = 0.0,
    val totalIncome: Double = 0.0,
    val undoEvent: UndoEvent? = null,     // non-null → show snackbar; cleared after consume
    // Import (Phase 3B) — sending the approved rows to the backend
    val isImporting: Boolean = false,
    val importSuccess: Boolean = false,
    val importError: String? = null,
    val importedCount: Int = 0,
    val failedCount: Int = 0
)

// ── ViewModel ─────────────────────────────────────────────────────────────

class UploadViewModel(
    application: Application,
    private val savedStateHandle: SavedStateHandle
) : AndroidViewModel(application) {

    private val repository: StatementRepository = StatementRepositoryImpl(
        apiService = RetrofitClient.buildStatementApiService(SessionManager(application)),
        contentResolver = application.contentResolver
    )

    private val _uiState = MutableStateFlow(
        UploadUiState(selectedFile = restoreFile())
    )
    val uiState: StateFlow<UploadUiState> = _uiState.asStateFlow()

    // ── File selection ─────────────────────────────────────────────────────

    fun onFileSelected(uri: Uri) {
        viewModelScope.launch {
            val resolved = withContext(Dispatchers.IO) { resolveFile(uri) }
            saveFile(resolved)
            _uiState.update {
                it.copy(
                    selectedFile = resolved,
                    uploadState = UploadState.Idle,
                    visibleTransactions = emptyList(),
                    removedTransactions = emptyList(),
                    totalExpense = 0.0,
                    totalIncome = 0.0,
                    undoEvent = null,
                    isImporting = false,
                    importSuccess = false,
                    importError = null,
                    importedCount = 0,
                    failedCount = 0
                )
            }
            Log.d("UploadViewModel", "File selected: ${resolved.name}")
        }
    }

    // ── Upload ─────────────────────────────────────────────────────────────

    fun onUpload() {
        val file = _uiState.value.selectedFile ?: return
        viewModelScope.launch {
            _uiState.update { it.copy(uploadState = UploadState.Uploading) }
            Log.d("UploadViewModel", "Uploading: ${file.name}")

            repository.uploadStatement(file.uri, file.name).fold(
                onSuccess = { response ->
                    Log.d("UploadViewModel", "Upload success: ${response.totalTransactions} transactions")
                    _uiState.update { state ->
                        state.copy(
                            uploadState = UploadState.Success(response),
                            visibleTransactions = response.transactions,
                            removedTransactions = emptyList(),
                            totalExpense = calcExpense(response.transactions),
                            totalIncome = calcIncome(response.transactions),
                            undoEvent = null,
                            isImporting = false,
                            importSuccess = false,
                            importError = null,
                            importedCount = 0,
                            failedCount = 0
                        )
                    }
                },
                onFailure = { ex ->
                    val msg = ex.message ?: "Upload failed. Please try again."
                    Log.e("UploadViewModel", "Upload failed: $msg")
                    _uiState.update { it.copy(uploadState = UploadState.Error(msg)) }
                }
            )
        }
    }

    // ── Preview management ─────────────────────────────────────────────────

    /** Remove a transaction from the visible list and queue the undo snackbar. */
    fun removeTransaction(transaction: ExtractedTransaction) {
        val current = _uiState.value.visibleTransactions
        val index = current.indexOf(transaction)
        if (index < 0) return

        val removed = RemovedTransaction(transaction, originalIndex = index)
        val newVisible = current.toMutableList().also { it.removeAt(index) }

        _uiState.update { state ->
            state.copy(
                visibleTransactions = newVisible,
                removedTransactions = state.removedTransactions + removed,
                totalExpense = calcExpense(newVisible),
                totalIncome = calcIncome(newVisible),
                undoEvent = UndoEvent(removed, id = System.currentTimeMillis())
            )
        }
        Log.d("UploadViewModel", "Removed: ${transaction.description}")
    }

    /** Re-insert the most recently removed transaction at its original position. */
    fun undoRemoveTransaction() {
        val state = _uiState.value
        val lastRemoved = state.removedTransactions.lastOrNull() ?: return

        val newVisible = state.visibleTransactions.toMutableList().also {
            val insertAt = minOf(lastRemoved.originalIndex, it.size)
            it.add(insertAt, lastRemoved.transaction)
        }

        _uiState.update {
            it.copy(
                visibleTransactions = newVisible,
                removedTransactions = it.removedTransactions.dropLast(1),
                totalExpense = calcExpense(newVisible),
                totalIncome = calcIncome(newVisible)
            )
        }
        Log.d("UploadViewModel", "Undo: restored ${lastRemoved.transaction.description}")
    }

    /** Clear the undo snackbar trigger after the screen has consumed it. */
    fun clearUndoEvent() {
        _uiState.update { it.copy(undoEvent = null) }
    }

    /** Restore all removed transactions to the visible list. */
    fun resetPreview() {
        val response = (_uiState.value.uploadState as? UploadState.Success)?.response ?: return
        _uiState.update {
            it.copy(
                visibleTransactions = response.transactions,
                removedTransactions = emptyList(),
                totalExpense = calcExpense(response.transactions),
                totalIncome = calcIncome(response.transactions),
                undoEvent = null
            )
        }
    }

    /** Returns the transactions the user has approved for import. */
    fun getTransactionsReadyForImport(): List<ExtractedTransaction> =
        _uiState.value.visibleTransactions

    // ── Import (Phase 3B) ────────────────────────────────────────────────────

    /**
     * Send only the visible (kept/edited) transactions to the backend import
     * endpoint. No-op if there is nothing to import or an import is in flight.
     */
    fun importSelectedTransactions() {
        val state = _uiState.value
        val response = (state.uploadState as? UploadState.Success)?.response ?: return
        val toImport = state.visibleTransactions
        if (toImport.isEmpty() || state.isImporting) return

        viewModelScope.launch {
            _uiState.update { it.copy(isImporting = true, importError = null) }
            Log.d("UploadViewModel", "Importing ${toImport.size} transactions for upload ${response.uploadId}")

            repository.importStatementTransactions(response.uploadId, toImport).fold(
                onSuccess = { result ->
                    Log.d(
                        "UploadViewModel",
                        "Import success: imported=${result.importedCount} failed=${result.failedCount}"
                    )
                    _uiState.update {
                        it.copy(
                            isImporting = false,
                            importSuccess = true,
                            importError = null,
                            importedCount = result.importedCount,
                            failedCount = result.failedCount
                        )
                    }
                },
                onFailure = { ex ->
                    Log.e("UploadViewModel", "Import failed: ${ex.message}")
                    _uiState.update {
                        it.copy(
                            isImporting = false,
                            importSuccess = false,
                            // Friendly message only — never surface raw backend errors.
                            importError = "Import failed. Please try again."
                        )
                    }
                }
            )
        }
    }

    /** Dismiss the import error so the user can retry. */
    fun clearImportError() {
        _uiState.update { it.copy(importError = null) }
    }

    // ── Full reset ─────────────────────────────────────────────────────────

    fun onReset() {
        clearSavedFile()
        _uiState.value = UploadUiState()
    }

    // ── Helpers ────────────────────────────────────────────────────────────

    private fun calcExpense(txns: List<ExtractedTransaction>) =
        txns.filter { it.amount < 0 }.sumOf { -it.amount }

    private fun calcIncome(txns: List<ExtractedTransaction>) =
        txns.filter { it.amount >= 0 }.sumOf { it.amount }

    private fun resolveFile(uri: Uri): SelectedFile {
        val cr = getApplication<Application>().contentResolver
        var name = uri.lastPathSegment ?: "statement.pdf"
        var size: Long? = null
        cr.query(uri, null, null, null, null)?.use { cursor ->
            val nameIdx = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
            val sizeIdx = cursor.getColumnIndex(OpenableColumns.SIZE)
            if (cursor.moveToFirst()) {
                if (nameIdx >= 0) name = cursor.getString(nameIdx) ?: name
                if (sizeIdx >= 0 && !cursor.isNull(sizeIdx)) size = cursor.getLong(sizeIdx)
            }
        }
        return SelectedFile(uri = uri, name = name, size = size)
    }

    private fun saveFile(file: SelectedFile) {
        savedStateHandle[KEY_URI]  = file.uri.toString()
        savedStateHandle[KEY_NAME] = file.name
        savedStateHandle[KEY_SIZE] = file.size ?: -1L
    }

    private fun clearSavedFile() {
        savedStateHandle.remove<String>(KEY_URI)
        savedStateHandle.remove<String>(KEY_NAME)
        savedStateHandle.remove<Long>(KEY_SIZE)
    }

    private fun restoreFile(): SelectedFile? {
        val uriStr = savedStateHandle.get<String>(KEY_URI) ?: return null
        val name   = savedStateHandle.get<String>(KEY_NAME) ?: return null
        val size   = savedStateHandle.get<Long>(KEY_SIZE).takeIf { it != null && it >= 0L }
        return SelectedFile(uri = Uri.parse(uriStr), name = name, size = size)
    }

    companion object {
        private const val KEY_URI  = "upload_file_uri"
        private const val KEY_NAME = "upload_file_name"
        private const val KEY_SIZE = "upload_file_size"
    }
}
