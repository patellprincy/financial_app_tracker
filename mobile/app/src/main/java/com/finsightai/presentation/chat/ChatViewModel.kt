package com.finsightai.presentation.chat

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.finsightai.data.repository.MockDataRepository
import com.finsightai.domain.model.ChatMessage
import com.finsightai.domain.model.MessageSender
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.time.LocalDateTime
import java.util.UUID

data class ChatUiState(
    val messages: List<ChatMessage> = emptyList(),
    val inputText: String = "",
    val isTyping: Boolean = false,
    val suggestedPrompts: List<String> = emptyList()
)

class ChatViewModel : ViewModel() {

    private val _uiState = MutableStateFlow(ChatUiState())
    val uiState: StateFlow<ChatUiState> = _uiState.asStateFlow()

    init {
        _uiState.update {
            it.copy(
                messages = MockDataRepository.getInitialChatMessages(),
                suggestedPrompts = MockDataRepository.suggestedChatPrompts
            )
        }
    }

    fun onInputChange(text: String) {
        _uiState.update { it.copy(inputText = text) }
    }

    fun sendMessage(content: String) {
        if (content.isBlank()) return

        val userMessage = ChatMessage(
            id = UUID.randomUUID().toString(),
            content = content,
            sender = MessageSender.USER,
            timestamp = LocalDateTime.now()
        )

        _uiState.update {
            it.copy(
                messages = it.messages + userMessage,
                inputText = "",
                isTyping = true
            )
        }

        viewModelScope.launch {
            delay(1000L + (500L * (1..3).random()))
            val reply = generateReply(content)
            val aiMessage = ChatMessage(
                id = UUID.randomUUID().toString(),
                content = reply,
                sender = MessageSender.AI,
                timestamp = LocalDateTime.now()
            )
            _uiState.update {
                it.copy(messages = it.messages + aiMessage, isTyping = false)
            }
        }
    }

    private fun generateReply(input: String): String {
        val key = input.lowercase().trim()
        return MockDataRepository.mockAiReplies.entries.find { (k, _) ->
            key.contains(k.substringBefore("?").take(15))
        }?.value ?: "I can help you analyze that. Based on your recent transactions, I can see clear patterns in your spending. Try asking me about specific categories or time periods for more details."
    }
}
