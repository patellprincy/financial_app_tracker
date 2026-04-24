package com.finsightai.presentation.upload

import android.app.Application
import android.net.Uri
import android.provider.OpenableColumns
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.viewModelScope
import com.finsightai.domain.model.SelectedFile
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

data class UploadUiState(
    val selectedFiles: List<SelectedFile> = emptyList(),
    val errorMessage: String? = null,
    val uploadMessage: String? = null
)

class UploadViewModel(
    application: Application,
    private val savedStateHandle: SavedStateHandle
) : AndroidViewModel(application) {

    private val _uiState = MutableStateFlow(UploadUiState(selectedFiles = restoreFiles()))
    val uiState: StateFlow<UploadUiState> = _uiState.asStateFlow()

    fun onFilesSelected(uris: List<Uri>) {
        if (uris.isEmpty()) return
        viewModelScope.launch {
            val resolved = withContext(Dispatchers.IO) { uris.map { resolveFile(it) } }
            val existing = _uiState.value.selectedFiles
            val existingUriStrings = existing.map { it.uri.toString() }.toSet()

            val newFiles = resolved.filter { candidate ->
                val uriMatch = candidate.uri.toString() in existingUriStrings
                val nameAndSizeMatch = candidate.size != null &&
                    existing.any { it.name == candidate.name && it.size == candidate.size }
                !uriMatch && !nameAndSizeMatch
            }
            val duplicateCount = resolved.size - newFiles.size

            val errorMessage = when {
                duplicateCount == 0 -> null
                newFiles.isEmpty() -> if (resolved.size == 1) "This file is already selected." else "All selected files are already added."
                else -> "Some files were already selected."
            }

            val updated = existing + newFiles
            if (newFiles.isNotEmpty()) saveFiles(updated)
            _uiState.update {
                it.copy(
                    selectedFiles = updated,
                    errorMessage = errorMessage,
                    uploadMessage = if (newFiles.isNotEmpty()) null else it.uploadMessage
                )
            }
        }
    }

    fun onUploadSelectedFiles() {
        _uiState.update { it.copy(uploadMessage = "Files are ready for processing.") }
    }

    fun clearErrorMessage() {
        _uiState.update { it.copy(errorMessage = null) }
    }

    private fun resolveFile(uri: Uri): SelectedFile {
        val contentResolver = getApplication<Application>().contentResolver
        var name = uri.lastPathSegment ?: "document.pdf"
        var size: Long? = null
        contentResolver.query(uri, null, null, null, null)?.use { cursor ->
            val nameIndex = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
            val sizeIndex = cursor.getColumnIndex(OpenableColumns.SIZE)
            if (cursor.moveToFirst()) {
                if (nameIndex >= 0) name = cursor.getString(nameIndex) ?: name
                if (sizeIndex >= 0 && !cursor.isNull(sizeIndex)) size = cursor.getLong(sizeIndex)
            }
        }
        return SelectedFile(uri = uri, name = name, size = size)
    }

    private fun saveFiles(files: List<SelectedFile>) {
        savedStateHandle[KEY_URIS] = ArrayList(files.map { it.uri.toString() })
        savedStateHandle[KEY_NAMES] = ArrayList(files.map { it.name })
        savedStateHandle[KEY_SIZES] = files.map { it.size ?: -1L }.toLongArray()
    }

    private fun restoreFiles(): List<SelectedFile> {
        val uris = savedStateHandle.get<ArrayList<String>>(KEY_URIS) ?: return emptyList()
        val names = savedStateHandle.get<ArrayList<String>>(KEY_NAMES) ?: return emptyList()
        val sizes = savedStateHandle.get<LongArray>(KEY_SIZES) ?: LongArray(uris.size) { -1L }
        return uris.indices.map { i ->
            SelectedFile(
                uri = Uri.parse(uris[i]),
                name = if (i < names.size) names[i] else uris[i],
                size = if (i < sizes.size && sizes[i] >= 0L) sizes[i] else null
            )
        }
    }

    companion object {
        private const val KEY_URIS = "selected_file_uris"
        private const val KEY_NAMES = "selected_file_names"
        private const val KEY_SIZES = "selected_file_sizes"
    }
}
