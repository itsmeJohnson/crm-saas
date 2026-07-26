package com.crm.mobile.feature.communication

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class ComposeUiState(
    val channel: Channel = Channel.SMS,
    val subject: String = "",
    val body: String = "",
    val sending: Boolean = false,
    val sent: Boolean = false,
    val error: String? = null,
)

@HiltViewModel
class ComposeViewModel @Inject constructor(
    savedStateHandle: SavedStateHandle,
    private val repo: CommunicationRepository,
) : ViewModel() {
    private val leadId: String = savedStateHandle["leadId"] ?: ""
    private val _ui = MutableStateFlow(ComposeUiState())
    val ui: StateFlow<ComposeUiState> = _ui.asStateFlow()

    fun setChannel(c: Channel) = _ui.update { it.copy(channel = c, error = null) }
    fun setSubject(s: String) = _ui.update { it.copy(subject = s) }
    fun setBody(b: String) = _ui.update { it.copy(body = b, error = null) }

    fun send() {
        val s = _ui.value
        if (s.body.isBlank()) return _ui.update { it.copy(error = "Type a message first.") }
        _ui.update { it.copy(sending = true, error = null) }
        viewModelScope.launch {
            repo.send(s.channel, leadId, s.subject, s.body)
                .onSuccess { _ui.update { st -> st.copy(sending = false, sent = true) } }
                .onFailure { e -> _ui.update { st -> st.copy(sending = false, error = e.message ?: "Send failed") } }
        }
    }
}

private val CHANNELS = listOf(Channel.SMS to "SMS", Channel.WHATSAPP to "WhatsApp", Channel.EMAIL to "Email")

@Composable
fun ComposeScreen(onDone: () -> Unit, vm: ComposeViewModel = hiltViewModel()) {
    val ui by vm.ui.collectAsStateWithLifecycle()

    if (ui.sent) {
        Column(Modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.Center) {
            Text("Message sent", style = MaterialTheme.typography.titleLarge)
            Text("It's been logged to the lead's timeline.", style = MaterialTheme.typography.bodyMedium)
            Button(onClick = onDone, modifier = Modifier.padding(top = 16.dp)) { Text("Done") }
        }
        return
    }

    Column(
        Modifier.fillMaxSize().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("New message", style = MaterialTheme.typography.titleLarge)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            CHANNELS.forEach { (ch, label) ->
                FilterChip(selected = ui.channel == ch, onClick = { vm.setChannel(ch) }, label = { Text(label) })
            }
        }
        if (ui.channel == Channel.EMAIL) {
            OutlinedTextField(ui.subject, vm::setSubject, label = { Text("Subject") },
                singleLine = true, modifier = Modifier.fillMaxWidth())
        }
        OutlinedTextField(ui.body, vm::setBody, label = { Text("Message") },
            modifier = Modifier.fillMaxWidth(), minLines = 4)
        ui.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        Button(onClick = vm::send, enabled = !ui.sending, modifier = Modifier.fillMaxWidth()) {
            if (ui.sending) CircularProgressIndicator(modifier = Modifier.padding(end = 8.dp))
            Text("Send")
        }
    }
}
