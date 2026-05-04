package com.finsightai.domain.model

import android.net.Uri

data class SelectedFile(
    val uri: Uri,
    val name: String,
    val size: Long?
)
