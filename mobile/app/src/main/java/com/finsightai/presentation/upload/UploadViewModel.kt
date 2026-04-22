package com.finsightai.presentation.upload

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.finsightai.data.repository.MockDataRepository
import com.finsightai.domain.model.Transaction
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class UploadUiState(
    val isLoading: Boolean = false,
    val previewTransactions: List<Transaction> = emptyList(),
    val importSuccess: Boolean = false
)

class UploadViewModel : ViewModel() {

    private val _uiState = MutableStateFlow(UploadUiState())
    val uiState: StateFlow<UploadUiState> = _uiState.asStateFlow()

    fun onUploadCsvClick() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, importSuccess = false) }
            delay(1500)
            _uiState.update {
                it.copy(
                    isLoading = false,
                    previewTransactions = MockDataRepository.transactions.take(8)
                )
            }
        }
    }

    fun onConfirmImport() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true) }
            delay(800)
            _uiState.update {
                it.copy(
                    isLoading = false,
                    previewTransactions = emptyList(),
                    importSuccess = true
                )
            }
        }
    }
}
