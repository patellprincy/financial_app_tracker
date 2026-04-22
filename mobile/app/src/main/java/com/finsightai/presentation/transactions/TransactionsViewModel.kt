package com.finsightai.presentation.transactions

import androidx.lifecycle.ViewModel
import com.finsightai.data.repository.MockDataRepository
import com.finsightai.domain.model.Transaction
import com.finsightai.domain.model.TransactionType
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update

data class TransactionsUiState(
    val searchQuery: String = "",
    val selectedFilter: String = "All",
    val filterOptions: List<String> = listOf("All", "Expenses", "Income", "Food", "Shopping", "Transport"),
    val allTransactions: List<Transaction> = emptyList(),
    val filteredTransactions: List<Transaction> = emptyList()
)

class TransactionsViewModel : ViewModel() {

    private val _uiState = MutableStateFlow(TransactionsUiState())
    val uiState: StateFlow<TransactionsUiState> = _uiState.asStateFlow()

    init {
        val transactions = MockDataRepository.transactions
        _uiState.update { it.copy(allTransactions = transactions, filteredTransactions = transactions) }
    }

    fun onSearchQueryChange(query: String) {
        _uiState.update { it.copy(searchQuery = query) }
        applyFilters()
    }

    fun onFilterSelect(filter: String) {
        _uiState.update { it.copy(selectedFilter = filter) }
        applyFilters()
    }

    private fun applyFilters() {
        val state = _uiState.value
        val filtered = state.allTransactions
            .filter { transaction ->
                val matchesSearch = state.searchQuery.isBlank() ||
                    transaction.merchant.contains(state.searchQuery, ignoreCase = true) ||
                    transaction.category.displayName.contains(state.searchQuery, ignoreCase = true)

                val matchesFilter = when (state.selectedFilter) {
                    "All" -> true
                    "Expenses" -> transaction.type == TransactionType.EXPENSE
                    "Income" -> transaction.type == TransactionType.INCOME
                    "Food" -> transaction.category.displayName.contains("Food", ignoreCase = true)
                    "Shopping" -> transaction.category.displayName.contains("Shopping", ignoreCase = true)
                    "Transport" -> transaction.category.displayName.contains("Transport", ignoreCase = true)
                    else -> true
                }

                matchesSearch && matchesFilter
            }

        _uiState.update { it.copy(filteredTransactions = filtered) }
    }
}
