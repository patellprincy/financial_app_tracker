package com.finsightai.presentation.addexpense

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class AddExpenseUiState(
    val merchant: String = "",
    val amount: String = "",
    val notes: String = "",
    val merchantError: String? = null,
    val amountError: String? = null,
    val notesError: String? = null,
    val isLoading: Boolean = false,
    val isSaved: Boolean = false
)

class AddExpenseViewModel : ViewModel() {

    private val _uiState = MutableStateFlow(AddExpenseUiState())
    val uiState: StateFlow<AddExpenseUiState> = _uiState.asStateFlow()

    fun onMerchantChange(value: String) = _uiState.update { it.copy(merchant = value, merchantError = null) }
    fun onAmountChange(value: String) = _uiState.update { it.copy(amount = value, amountError = null) }
    fun onNotesChange(value: String) = _uiState.update { it.copy(notes = value, notesError = null) }

    fun saveManualTransaction(merchant: String, amount: String, notes: String) {
        val merchantError = if (merchant.isBlank()) "Merchant is required" else null
        val amountError = when {
            amount.isBlank() -> "Amount is required"
            amount.toDoubleOrNull() == null -> "Enter a valid decimal number"
            amount.toDouble() <= 0 -> "Amount must be greater than zero"
            else -> null
        }
        val notesError = if (notes.isBlank()) "Notes is required" else null

        if (merchantError != null || amountError != null || notesError != null) {
            _uiState.update {
                it.copy(
                    merchantError = merchantError,
                    amountError = amountError,
                    notesError = notesError
                )
            }
            return
        }

        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true) }
            // API call will be wired here
            _uiState.update { it.copy(isLoading = false, isSaved = true) }
        }
    }
}
