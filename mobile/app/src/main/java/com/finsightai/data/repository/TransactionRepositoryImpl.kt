package com.finsightai.data.repository

import android.util.Log
import com.finsightai.data.network.ManualTransactionRequest
import com.finsightai.data.network.TransactionApiService
import com.finsightai.domain.model.CategoryBreakdown
import com.finsightai.domain.model.DashboardData
import com.finsightai.domain.model.DashboardSummary
import com.finsightai.domain.model.Transaction
import com.finsightai.domain.model.TransactionType
import com.finsightai.domain.repository.TransactionRepository
import retrofit2.HttpException
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import kotlin.math.abs

class TransactionRepositoryImpl(
    private val apiService: TransactionApiService
) : TransactionRepository {

    override suspend fun addManualTransaction(
        merchant: String,
        amount: Double,
        notes: String
    ): Result<Transaction> = runCatching {
        Log.d("TransactionRepo", "addManualTransaction: calling API — merchant=$merchant")
        val request = ManualTransactionRequest(merchant, amount, notes)
        val response = apiService.addManualTransaction(request)
        Log.d("TransactionRepo", "addManualTransaction: success — id=${response.id}")
        response.toDomain()
    }.onFailure { ex ->
        when (ex) {
            is HttpException -> Log.e("TransactionRepo", "addManualTransaction: HTTP ${ex.code()} ${ex.message()}")
            else -> Log.e("TransactionRepo", "addManualTransaction: ${ex.javaClass.simpleName} — ${ex.message}")
        }
    }

    override suspend fun getTransactions(): Result<List<Transaction>> = runCatching {
        Log.d("TransactionRepo", "getTransactions: calling API")
        val response = apiService.getTransactions()
        Log.d("TransactionRepo", "getTransactions: success — count=${response.size}")
        response.map { it.toDomain() }
    }.onFailure { ex ->
        when (ex) {
            is HttpException -> Log.e("TransactionRepo", "getTransactions: HTTP ${ex.code()} ${ex.message()}")
            else -> Log.e("TransactionRepo", "getTransactions: ${ex.javaClass.simpleName} — ${ex.message}")
        }
    }

    override suspend fun getTransactionById(transactionId: String): Result<Transaction> = runCatching {
        Log.d("TransactionRepo", "getTransactionById: calling API — transactionId=$transactionId")
        val response = apiService.getTransactionById(transactionId)
        Log.d("TransactionRepo", "getTransactionById: success — merchant=${response.merchant}")
        response.toDomain()
    }.onFailure { ex ->
        when (ex) {
            is HttpException -> Log.e("TransactionRepo", "getTransactionById: HTTP ${ex.code()} ${ex.message()}")
            else -> Log.e("TransactionRepo", "getTransactionById: ${ex.javaClass.simpleName} — ${ex.message}")
        }
    }

    override suspend fun getDashboard(): Result<DashboardData> = runCatching {
        Log.d("TransactionRepo", "getDashboard: calling API")
        val response = apiService.getDashboard()
        Log.d("TransactionRepo", "getDashboard: success")

        val topCategory = response.categoryBreakdown
            .maxByOrNull { abs(it.amount) }
            ?.categoryName
            ?: ""

        val summary = DashboardSummary(
            totalExpenses = response.totalExpense,
            totalIncome = response.totalIncome,
            topCategory = topCategory
        )

        val breakdown = response.categoryBreakdown.map { dto ->
            CategoryBreakdown(
                categoryId = dto.categoryId,
                categoryName = dto.categoryName,
                amount = dto.amount,
                percentage = dto.percentage.toFloat()
            )
        }

        val transactions = response.recentTransactions.map { it.toDomain() }

        DashboardData(
            summary = summary,
            categoryBreakdown = breakdown,
            recentTransactions = transactions
        )
    }.onFailure { ex ->
        when (ex) {
            is HttpException -> Log.e("TransactionRepo", "getDashboard: HTTP ${ex.code()} ${ex.message()}")
            else -> Log.e("TransactionRepo", "getDashboard: ${ex.javaClass.simpleName} — ${ex.message}")
        }
    }

    private fun com.finsightai.data.network.TransactionDto.toDomain(): Transaction {
        val formatter = DateTimeFormatter.ISO_OFFSET_DATE_TIME
        val date = try {
            LocalDate.parse(createdAt, formatter)
        } catch (e: Exception) {
            LocalDate.now()
        }

        return Transaction(
            id = id.toString(),
            merchant = merchant,
            categoryId = categoryId,
            categoryName = categoryName,
            amount = amount,
            date = date,
            notes = notes,
            type = if (transactionType.lowercase() == "income") TransactionType.INCOME else TransactionType.EXPENSE
        )
    }
}
