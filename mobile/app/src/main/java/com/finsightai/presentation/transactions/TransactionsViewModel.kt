package com.finsightai.presentation.transactions

import android.app.Application
import android.util.Log
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.finsightai.data.local.SessionManager
import com.finsightai.data.network.RetrofitClient
import com.finsightai.data.repository.TransactionRepositoryImpl
import com.finsightai.domain.model.Transaction
import com.finsightai.domain.model.TransactionType
import com.finsightai.domain.repository.TransactionRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import retrofit2.HttpException

data class TransactionsUiState(
    val isLoading: Boolean = false,
    val error: String? = null,
    val searchQuery: String = "",
    val selectedFilter: String = "All",
    val filterOptions: List<String> = listOf("All", "Expenses", "Income"),
    val allTransactions: List<Transaction> = emptyList(),
    val filteredTransactions: List<Transaction> = emptyList()
) {
    val isEmpty: Boolean get() = !isLoading && error == null && allTransactions.isEmpty()
}

class TransactionsViewModel(application: Application) : AndroidViewModel(application) {

    private val sessionManager = SessionManager(application)
    private val repository: TransactionRepository = TransactionRepositoryImpl(
        RetrofitClient.buildTransactionApiService(sessionManager)
    )

    private val _uiState = MutableStateFlow(TransactionsUiState())
    val uiState: StateFlow<TransactionsUiState> = _uiState.asStateFlow()

//    init {
//        loadTransactions()
//    }

    fun loadTransactions() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, error = null) }
            Log.d("TransactionsViewModel", "loadTransactions: starting API call")

            repository.getTransactions()
                .onSuccess { transactions ->
                    Log.d("TransactionsViewModel", "loadTransactions: success — count=${transactions.size}")
                    _uiState.update {
                        it.copy(
                            isLoading = false,
                            allTransactions = transactions,
                            filteredTransactions = transactions
                        )
                    }
                    applyFilters()
                }
                .onFailure { ex ->
                    val errorMsg = when (ex) {
                        is HttpException -> {
                            val msg = "HTTP ${ex.code()}: ${ex.message()}"
                            Log.e("TransactionsViewModel", "loadTransactions: $msg")
                            msg
                        }
                        else -> {
                            val msg = "${ex.javaClass.simpleName}: ${ex.message}"
                            Log.e("TransactionsViewModel", "loadTransactions: $msg")
                            msg
                        }
                    }
                    _uiState.update { it.copy(isLoading = false, error = errorMsg) }
                }
        }
    }

    fun onSearchQueryChange(query: String) {
        Log.d("TransactionsViewModel", "onSearchQueryChange: query=$query")
        _uiState.update { it.copy(searchQuery = query) }
        applyFilters()
    }

    fun onFilterSelect(filter: String) {
        Log.d("TransactionsViewModel", "onFilterSelect: filter=$filter")
        _uiState.update { it.copy(selectedFilter = filter) }
        applyFilters()
    }

    private fun applyFilters() {
        val state = _uiState.value
        val filtered = state.allTransactions.filter { transaction ->
            val matchesSearch = state.searchQuery.isBlank() ||
                transaction.merchant.contains(state.searchQuery, ignoreCase = true) ||
                transaction.categoryName.contains(state.searchQuery, ignoreCase = true)

            val matchesFilter = when (state.selectedFilter) {
                "All" -> true
                "Expenses" -> transaction.type == TransactionType.EXPENSE
                "Income" -> transaction.type == TransactionType.INCOME
                else -> true
            }

            matchesSearch && matchesFilter
        }
        Log.d("TransactionsViewModel", "applyFilters: filtered=${filtered.size} from ${state.allTransactions.size}")
        _uiState.update { it.copy(filteredTransactions = filtered) }
    }
}
