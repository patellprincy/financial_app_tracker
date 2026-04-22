package com.finsightai.domain.model

import java.time.LocalDateTime

data class ChatMessage(
    val id: String,
    val content: String,
    val sender: MessageSender,
    val timestamp: LocalDateTime = LocalDateTime.now()
)

enum class MessageSender {
    USER, AI
}
