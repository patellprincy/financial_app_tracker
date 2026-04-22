package com.finsightai.presentation.addexpense

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.finsightai.domain.model.TransactionCategory
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.time.LocalDate
import java.time.format.DateTimeFormatter

data class AddExpenseUiState(
    val amount: String = "",
    val selectedCategory: TransactionCategory = TransactionCategory.OTHER,
    val merchant: String = "",
    val date: String = LocalDate.now().format(DateTimeFormatter.ofPattern("dd/MM/yyyy")),
    val notes: String = "",
    val isSaved: Boolean = false
)

class AddExpenseViewModel : ViewModel() {

    private val _uiState = MutableStateFlow(AddExpenseUiState())
    val uiState: StateFlow<AddExpenseUiState> = _uiState.asStateFlow()

    fun onAmountChange(value: String) = _uiState.update { it.copy(amount = value) }
    fun onCategorySelect(category: TransactionCategory) = _uiState.update { it.copy(selectedCategory = category) }
    fun onMerchantChange(value: String) = _uiState.update { it.copy(merchant = value) }
    fun onDateChange(value: String) = _uiState.update { it.copy(date = value) }
    fun onNotesChange(value: String) = _uiState.update { it.copy(notes = value) }

    fun onSave(onComplete: () -> Unit) {
        viewModelScope.launch {
            _uiState.update { it.copy(isSaved = true) }
            delay(800)
            onComplete()
        }
    }
}
