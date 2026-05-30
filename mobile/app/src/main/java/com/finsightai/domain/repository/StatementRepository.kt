package com.finsightai.domain.repository

import android.net.Uri
import com.finsightai.domain.model.StatementUploadResponse

interface StatementRepository {
    suspend fun uploadStatement(uri: Uri, fileName: String): Result<StatementUploadResponse>
}
