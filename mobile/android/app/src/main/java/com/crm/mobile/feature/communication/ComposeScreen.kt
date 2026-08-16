package com.crm.mobile.feature.communication

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.crm.mobile.core.design.DentalColors
import com.crm.mobile.core.util.PhoneActions
import com.crm.mobile.feature.leads.Lead
import com.crm.mobile.feature.leads.LeadRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class ComposeUiState(
    val channel: Channel = Channel.WHATSAPP,
    val recipientPhone: String = "",
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
    private val leadRepo: LeadRepository,
) : ViewModel() {
    val leadId: String = savedStateHandle["leadId"] ?: ""
    private val _ui = MutableStateFlow(ComposeUiState())
    val ui: StateFlow<ComposeUiState> = _ui.asStateFlow()

    val leadsList: StateFlow<List<Lead>> =
        leadRepo.leads.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    init {
        viewModelScope.launch {
            leadRepo.leads.collect { list ->
                val lead = list.find { it.id == leadId }
                if (lead != null && !lead.phone.isNullOrBlank() && _ui.value.recipientPhone.isBlank()) {
                    _ui.update { it.copy(recipientPhone = lead.phone) }
                }
            }
        }
    }

    fun setRecipientPhone(phone: String) = _ui.update { it.copy(recipientPhone = phone, error = null) }
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

private val CHANNELS = listOf(Channel.WHATSAPP to "WhatsApp", Channel.SMS to "SMS", Channel.EMAIL to "Email")

@Composable
fun ComposeScreen(onDone: () -> Unit, vm: ComposeViewModel = hiltViewModel()) {
    val context = LocalContext.current
    val ui by vm.ui.collectAsStateWithLifecycle()
    val allLeads by vm.leadsList.collectAsStateWithLifecycle()
    var showLeadPicker by remember { mutableStateOf(false) }

    if (ui.sent) {
        Column(
            Modifier.fillMaxSize().padding(24.dp),
            verticalArrangement = Arrangement.Center,
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text("✅ Message Sent / Logged", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
            Text("Saved to customer conversation history.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Button(
                onClick = onDone,
                colors = ButtonDefaults.buttonColors(containerColor = DentalColors.Teal600),
                shape = RoundedCornerShape(10.dp),
                modifier = Modifier.padding(top = 16.dp)
            ) {
                Text("Back to Dashboard", fontWeight = FontWeight.Bold)
            }
        }
        return
    }

    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Text("Quick Customer Messaging", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)

        // Channel Selector
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            CHANNELS.forEach { (ch, label) ->
                FilterChip(
                    selected = ui.channel == ch,
                    onClick = { vm.setChannel(ch) },
                    label = { Text(label, fontWeight = if (ui.channel == ch) FontWeight.Bold else FontWeight.Normal) }
                )
            }
        }

        // Recipient Phone Input Card with Lead Picker Dropdown
        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(12.dp),
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
            border = CardDefaults.outlinedCardBorder().copy(
                brush = SolidColor(MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.6f))
            )
        ) {
            Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        "RECIPIENT CONTACT",
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.primary
                    )

                    if (allLeads.isNotEmpty()) {
                        Box {
                            OutlinedButton(
                                onClick = { showLeadPicker = true },
                                shape = RoundedCornerShape(6.dp),
                                modifier = Modifier.height(30.dp)
                            ) {
                                Text("Choose from Leads ▾", style = MaterialTheme.typography.labelSmall)
                            }
                            DropdownMenu(
                                expanded = showLeadPicker,
                                onDismissRequest = { showLeadPicker = false }
                            ) {
                                allLeads.filter { !it.phone.isNullOrBlank() }.take(10).forEach { l ->
                                    DropdownMenuItem(
                                        text = { Text("${l.name} (${l.phone})") },
                                        onClick = {
                                            vm.setRecipientPhone(l.phone ?: "")
                                            showLeadPicker = false
                                        }
                                    )
                                }
                            }
                        }
                    }
                }

                OutlinedTextField(
                    value = ui.recipientPhone,
                    onValueChange = vm::setRecipientPhone,
                    label = { Text("Phone Number / Mobile *") },
                    placeholder = { Text("+91 98765 43210") },
                    singleLine = true,
                    shape = RoundedCornerShape(10.dp),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone),
                    modifier = Modifier.fillMaxWidth()
                )
            }
        }

        if (ui.channel == Channel.EMAIL) {
            OutlinedTextField(
                value = ui.subject,
                onValueChange = vm::setSubject,
                label = { Text("Subject") },
                singleLine = true,
                shape = RoundedCornerShape(10.dp),
                modifier = Modifier.fillMaxWidth()
            )
        }

        OutlinedTextField(
            value = ui.body,
            onValueChange = vm::setBody,
            label = { Text("Message Text") },
            placeholder = { Text("Hi, following up on your inquiry with FewClick CRM...") },
            shape = RoundedCornerShape(10.dp),
            modifier = Modifier.fillMaxWidth(),
            minLines = 4
        )

        ui.error?.let {
            Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
        }

        // Action Buttons: 1-Tap Direct WhatsApp Launch & 1-Tap SIM Call
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            Button(
                onClick = {
                    val phone = ui.recipientPhone.ifBlank { null }
                    PhoneActions.launchWhatsApp(context, phone, ui.body.ifBlank { null })
                },
                enabled = ui.recipientPhone.isNotBlank(),
                shape = RoundedCornerShape(10.dp),
                colors = ButtonDefaults.buttonColors(containerColor = DentalColors.Teal600),
                modifier = Modifier.weight(1f).height(48.dp)
            ) {
                Text("💬 WhatsApp App", fontWeight = FontWeight.Bold)
            }

            Button(
                onClick = {
                    val phone = ui.recipientPhone.ifBlank { null }
                    PhoneActions.launchDialer(context, phone)
                },
                enabled = ui.recipientPhone.isNotBlank(),
                shape = RoundedCornerShape(10.dp),
                colors = ButtonDefaults.buttonColors(containerColor = DentalColors.Teal700),
                modifier = Modifier.weight(1f).height(48.dp)
            ) {
                Text("📞 SIM Dialer", fontWeight = FontWeight.Bold)
            }
        }

        OutlinedButton(
            onClick = vm::send,
            enabled = !ui.sending,
            shape = RoundedCornerShape(10.dp),
            modifier = Modifier.fillMaxWidth().height(44.dp)
        ) {
            if (ui.sending) CircularProgressIndicator(modifier = Modifier.padding(end = 8.dp))
            Text("☁️ Log & Sync with CRM Timeline")
        }

        Box(Modifier.padding(bottom = 20.dp)) {}
    }
}
