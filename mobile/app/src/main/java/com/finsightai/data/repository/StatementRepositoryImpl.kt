package com.finsightai.data.repository

import android.content.ContentResolver
import android.net.Uri
import android.util.Log
import com.finsightai.data.network.StatementApiService
import com.finsightai.domain.model.ExtractedTransaction
import com.finsightai.domain.model.StatementUploadResponse
import com.finsightai.domain.repository.StatementRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody
import retrofit2.HttpException
import java.io.IOException

class StatementRepositoryImpl(
    private val apiService: StatementApiService,
    private val contentResolver: ContentResolver
) : StatementRepository {

    override suspend fun uploadStatement(uri: Uri, fileName: String): Result<StatementUploadResponse> =
        runCatching {
            Log.d("StatementRepo", "uploadStatement: reading file — $fileName")

            val bytes = withContext(Dispatchers.IO) {
                contentResolver.openInputStream(uri)
                    ?.use { it.readBytes() }
                    ?: throw IOException("Cannot open PDF: $fileName")
            }

            Log.d("StatementRepo", "uploadStatement: file read — ${bytes.size} bytes, uploading")

            val requestBody = bytes.toRequestBody("application/pdf".toMediaType())
            val filePart = MultipartBody.Part.createFormData("file", fileName, requestBody)
            val dto = apiService.uploadStatement(filePart)

            Log.d("StatementRepo", "uploadStatement: success — status=${dto.status}, transactions=${dto.totalTransactions}")

            StatementUploadResponse(
                uploadId = dto.uploadId,
                fileName = dto.fileName,
                status = dto.status,
                totalTransactions = dto.totalTransactions,
                transactions = dto.transactions.map { t ->
                    ExtractedTransaction(
                        transactionDate = t.transactionDate,
                        description = t.description,
                        amount = t.amount,
                        rawText = t.rawText
                    )
                },
                parseError = dto.parseError
            )
        }.onFailure { ex ->
            when (ex) {
                is HttpException -> Log.e("StatementRepo", "uploadStatement: HTTP ${ex.code()} — ${ex.message()}")
                is IOException   -> Log.e("StatementRepo", "uploadStatement: IO error — ${ex.message}")
                else             -> Log.e("StatementRepo", "uploadStatement: ${ex.javaClass.simpleName} — ${ex.message}")
            }
        }
}
