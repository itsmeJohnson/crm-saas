package com.crm.mobile.feature.cockpit

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.ZoneId
import javax.inject.Inject

private val OUTBOUND_DISPOSITIONS =
    listOf("RNR", "Switch Off", "Busy", "Not Exist", "Out of Service", "Picked", "Interested", "Follow-up")
private val STAGE_REQUIRED = setOf("Picked", "Interested")
private const val FOLLOW_UP = "Follow-up"
private val FOLLOW_PRESETS = listOf("Later today", "Tomorrow", "In 3 days", "Next week")
private val PRIORITIES = listOf("Low", "Medium", "High", "Urgent")
private val REMINDERS = listOf(15, 30, 60)

data class CockpitForm(
    val status: String? = null,
    val remarks: String = "",
    val stageId: String? = null,
    val whenPreset: String? = null,
    val priority: String = "Medium",
    val reminderMinutes: Int = 30,
    val calendarEvent: Boolean = false,
)

data class CockpitUiState(
    val loading: Boolean = true,
    val saving: Boolean = false,
    val calling: Boolean = false,
    val callMessage: String? = null,
    val error: String? = null,
    val form: CockpitForm = CockpitForm(),
)

@HiltViewModel
class CockpitViewModel @Inject constructor(
    private val repo: CockpitRepository,
) : ViewModel() {

    private val _lead = MutableStateFlow<CockpitLead?>(null)
    val lead: StateFlow<CockpitLead?> = _lead.asStateFlow()

    val stages: StateFlow<List<Stage>> =
        repo.stages.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    private val _ui = MutableStateFlow(CockpitUiState())
    val ui: StateFlow<CockpitUiState> = _ui.asStateFlow()

    init {
        viewModelScope.launch { repo.refreshStages() }
        loadNext()
    }

    fun loadNext() {
        _ui.update { it.copy(loading = true, error = null, callMessage = null, form = CockpitForm()) }
        viewModelScope.launch {
            _lead.value = repo.nextLead()
            _ui.update { it.copy(loading = false) }
        }
    }

    fun placeCall() {
        val id = _lead.value?.id ?: return
        _ui.update { it.copy(calling = true, callMessage = null) }
        viewModelScope.launch {
            val res = repo.call(id)
            _ui.update { it.copy(calling = false, callMessage = res.message ?: "Call started") }
        }
    }

    fun update(transform: (CockpitForm) -> CockpitForm) =
        _ui.update { it.copy(form = transform(it.form), error = null) }

    fun save() {
        val id = _lead.value?.id ?: return
        val f = _ui.value.form
        val status = f.status ?: return _ui.update { it.copy(error = "Pick an outcome first.") }
        if (f.remarks.isBlank()) return _ui.update { it.copy(error = "Remarks are required.") }
        if (status in STAGE_REQUIRED && f.stageId == null)
            return _ui.update { it.copy(error = "Select a pipeline stage for this outcome.") }
        if (status == FOLLOW_UP && f.whenPreset == null)
            return _ui.update { it.copy(error = "Choose when to follow up.") }

        _ui.update { it.copy(saving = true, error = null) }
        viewModelScope.launch {
            val result = if (status == FOLLOW_UP) {
                repo.submitFollowUp(id, FOLLOW_UP, computeIso(f.whenPreset!!), f.priority,
                    f.remarks, f.reminderMinutes, f.calendarEvent)
            } else {
                repo.submitDisposition(id, status, f.remarks, f.stageId)
            }
            result.onSuccess { loadNext() }
                .onFailure { e -> _ui.update { it.copy(saving = false, error = e.message ?: "Save failed") } }
        }
    }

    private fun computeIso(preset: String): String {
        val zone = ZoneId.systemDefault()
        val base = LocalDate.now(zone)
        val dt = when (preset) {
            "Later today" -> LocalDateTime.now(zone).plusHours(3)
            "Tomorrow" -> base.plusDays(1).atTime(10, 0)
            "In 3 days" -> base.plusDays(3).atTime(10, 0)
            "Next week" -> base.plusWeeks(1).atTime(10, 0)
            else -> LocalDateTime.now(zone).plusHours(1)
        }
        return dt.atZone(zone).toInstant().toString()
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun CockpitScreen(onMessage: (String) -> Unit = {}, vm: CockpitViewModel = hiltViewModel()) {
    val lead by vm.lead.collectAsStateWithLifecycle()
    val stages by vm.stages.collectAsStateWithLifecycle()
    val ui by vm.ui.collectAsStateWithLifecycle()
    val l = lead

    when {
        ui.loading -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
        l == null -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text("No uncalled leads in your queue", style = MaterialTheme.typography.titleMedium)
                Button(onClick = vm::loadNext, modifier = Modifier.padding(top = 12.dp)) { Text("Refresh") }
            }
        }
        else -> Column(
            Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            // Customer card
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp)) {
                    Text(l.title, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                    Text(l.name, style = MaterialTheme.typography.bodyLarge)
                    l.phone?.let { Text(it, style = MaterialTheme.typography.bodyMedium) }
                    Text(listOfNotNull(l.city, l.status).joinToString(" · "),
                        style = MaterialTheme.typography.bodySmall)
                }
            }

            Button(onClick = vm::placeCall, enabled = !ui.calling, modifier = Modifier.fillMaxWidth()) {
                Text(if (ui.calling) "Calling…" else "Call customer")
            }
            ui.callMessage?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
            OutlinedButton(onClick = { onMessage(l.id) }, modifier = Modifier.fillMaxWidth()) {
                Text("Message (SMS / WhatsApp / Email)")
            }

            SectionLabel("Outcome")
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OUTBOUND_DISPOSITIONS.forEach { d ->
                    FilterChip(selected = ui.form.status == d, onClick = { vm.update { it.copy(status = d) } },
                        label = { Text(d) })
                }
            }

            OutlinedTextField(
                value = ui.form.remarks, onValueChange = { v -> vm.update { it.copy(remarks = v) } },
                label = { Text("Remarks") }, modifier = Modifier.fillMaxWidth(), minLines = 2,
            )

            if (ui.form.status in STAGE_REQUIRED) {
                SectionLabel("Pipeline stage")
                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    stages.forEach { s ->
                        FilterChip(selected = ui.form.stageId == s.id,
                            onClick = { vm.update { it.copy(stageId = s.id) } }, label = { Text(s.name) })
                    }
                }
            }

            if (ui.form.status == FOLLOW_UP) {
                SectionLabel("Follow up when")
                ChipRow(FOLLOW_PRESETS, ui.form.whenPreset) { p -> vm.update { it.copy(whenPreset = p) } }
                SectionLabel("Priority")
                ChipRow(PRIORITIES, ui.form.priority) { p -> vm.update { it.copy(priority = p) } }
                SectionLabel("Remind me before")
                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    REMINDERS.forEach { m ->
                        FilterChip(selected = ui.form.reminderMinutes == m,
                            onClick = { vm.update { it.copy(reminderMinutes = m) } }, label = { Text("$m min") })
                    }
                }
                OutlinedButton(onClick = { vm.update { it.copy(calendarEvent = !it.calendarEvent) } }) {
                    Text(if (ui.form.calendarEvent) "✓ Add to calendar" else "Add to calendar")
                }
            }

            ui.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }

            Button(onClick = vm::save, enabled = !ui.saving, modifier = Modifier.fillMaxWidth().padding(top = 4.dp)) {
                Text(if (ui.saving) "Saving…" else "Save outcome")
            }
            Box(Modifier.padding(bottom = 24.dp)) {}
        }
    }
}

@Composable
private fun SectionLabel(text: String) =
    Text(text, style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.SemiBold)

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun ChipRow(options: List<String>, selected: String?, onSelect: (String) -> Unit) {
    FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        options.forEach { o -> FilterChip(selected = selected == o, onClick = { onSelect(o) }, label = { Text(o) }) }
    }
}
