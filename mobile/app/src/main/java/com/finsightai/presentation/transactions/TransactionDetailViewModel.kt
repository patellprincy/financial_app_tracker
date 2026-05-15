package com.finsightai.presentation.transactions

import android.app.Application
import android.util.Log
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.finsightai.data.local.SessionManager
import com.finsightai.data.network.RetrofitClient
import com.finsightai.data.repository.TransactionRepositoryImpl
import com.finsightai.domain.model.Transaction
import com.finsightai.domain.repository.TransactionRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import retrofit2.HttpException

data class TransactionDetailUiState(
    val isLoading: Boolean = false,
    val error: String? = null,
    val transaction: Transaction? = null
) {
    val isEmpty: Boolean get() = !isLoading && error == null && transaction == null
}

class TransactionDetailViewModel(application: Application) : AndroidViewModel(application) {

    private val sessionManager = SessionManager(application)
    private val repository: TransactionRepository = TransactionRepositoryImpl(
        RetrofitClient.buildTransactionApiService(sessionManager)
    )

    private val _uiState = MutableStateFlow(TransactionDetailUiState())
    val uiState: StateFlow<TransactionDetailUiState> = _uiState.asStateFlow()

    fun loadTransaction(transactionId: String) {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, error = null) }
            Log.d("TransactionDetailVM", "loadTransaction: starting API call — transactionId=$transactionId")

            repository.getTransactionById(transactionId)
                .onSuccess { transaction ->
                    Log.d("TransactionDetailVM", "loadTransaction: success — merchant=${transaction.merchant}")
                    _uiState.update {
                        it.copy(
                            isLoading = false,
                            transaction = transaction
                        )
                    }
                }
                .onFailure { ex ->
                    val errorMsg = when (ex) {
                        is HttpException -> {
                            val msg = when (ex.code()) {
                                404 -> "Transaction not found"
                                401, 403 -> "Unauthorized access"
                                else -> "HTTP ${ex.code()}: ${ex.message()}"
                            }
                            Log.e("TransactionDetailVM", "loadTransaction: $msg")
                            msg
                        }
                        else -> {
                            val msg = "${ex.javaClass.simpleName}: ${ex.message}"
                            Log.e("TransactionDetailVM", "loadTransaction: $msg")
                            msg
                        }
                    }
                    _uiState.update { it.copy(isLoading = false, error = errorMsg) }
                }
        }
    }
}
