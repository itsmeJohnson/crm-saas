package com.crm.mobile.feature.reminders

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.crm.mobile.core.design.DentalColors
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.ZoneId
import java.util.Date
import java.util.Locale
import javax.inject.Inject

@HiltViewModel
class ReminderViewModel @Inject constructor(private val repo: ReminderRepository) : ViewModel() {
    private val _loading = MutableStateFlow(true)
    val loading: StateFlow<Boolean> = _loading.asStateFlow()
    private val _offline = MutableStateFlow(false)
    val offline: StateFlow<Boolean> = _offline.asStateFlow()

    val grouped: StateFlow<Map<ReminderBucket, List<Reminder>>> = repo.reminders
        .map { group(it) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyMap())

    init { refresh() }

    fun refresh() {
        _loading.value = true
        viewModelScope.launch { _offline.value = !repo.refresh(); _loading.value = false }
    }

    fun snooze(r: Reminder, option: SnoozeOption) = viewModelScope.launch {
        repo.snooze(r.id, option.nextMillis(System.currentTimeMillis()))
    }

    fun complete(r: Reminder) = viewModelScope.launch { repo.complete(r.id) }

    fun createReminder(
        title: String,
        notes: String?,
        preset: String,
        priority: String,
        onDone: () -> Unit
    ) {
        if (title.isBlank()) return
        viewModelScope.launch {
            val iso = computeIso(preset)
            repo.create(title, notes, priority, iso)
            onDone()
        }
    }

    private fun computeIso(preset: String): String {
        val zone = ZoneId.systemDefault()
        val base = LocalDate.now(zone)
        val dt = when (preset) {
            "In 1 hour" -> LocalDateTime.now(zone).plusHours(1)
            "Later today" -> LocalDateTime.now(zone).plusHours(3)
            "Tomorrow 10am" -> base.plusDays(1).atTime(10, 0)
            "In 3 days" -> base.plusDays(3).atTime(10, 0)
            "Next week" -> base.plusWeeks(1).atTime(10, 0)
            else -> LocalDateTime.now(zone).plusHours(2)
        }
        return dt.atZone(zone).toInstant().toString()
    }

    private fun group(list: List<Reminder>): Map<ReminderBucket, List<Reminder>> {
        val zone = ZoneId.systemDefault()
        val today = LocalDate.now(zone)
        val start = today.atStartOfDay(zone).toInstant().toEpochMilli()
        val end = today.plusDays(1).atStartOfDay(zone).toInstant().toEpochMilli()
        return list.groupBy { it.bucket(start, end) }
    }
}

private val SECTION_ORDER = listOf(
    ReminderBucket.OVERDUE, ReminderBucket.TODAY, ReminderBucket.UPCOMING, ReminderBucket.COMPLETED,
)

private fun ReminderBucket.label() = when (this) {
    ReminderBucket.OVERDUE -> "Overdue"
    ReminderBucket.TODAY -> "Today"
    ReminderBucket.UPCOMING -> "Upcoming"
    ReminderBucket.COMPLETED -> "Completed"
}

private val REMINDER_PRESETS = listOf("In 1 hour", "Later today", "Tomorrow 10am", "In 3 days", "Next week")
private val PRIORITIES = listOf("Low", "Medium", "High", "Urgent")

@Composable
fun ReminderScreen(onOpenLead: (String) -> Unit, vm: ReminderViewModel = hiltViewModel()) {
    val loading by vm.loading.collectAsStateWithLifecycle()
    val offline by vm.offline.collectAsStateWithLifecycle()
    val grouped by vm.grouped.collectAsStateWithLifecycle()
    val total = grouped.values.sumOf { it.size }
    var showCreateDialog by remember { mutableStateOf(false) }

    Scaffold(
        floatingActionButton = {
            FloatingActionButton(
                onClick = { showCreateDialog = true },
                containerColor = DentalColors.Teal600,
                contentColor = Color.White,
                shape = RoundedCornerShape(16.dp)
            ) {
                Row(
                    modifier = Modifier.padding(horizontal = 16.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(6.dp)
                ) {
                    Text("⏰", fontSize = 18.sp)
                    Text("+ Create Reminder", fontWeight = FontWeight.Bold)
                }
            }
        }
    ) { padding ->
        Column(
            Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 14.dp)
        ) {
            if (offline) {
                Text(
                    "⚠️ Offline — showing cached reminders",
                    color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.labelSmall,
                    modifier = Modifier.padding(vertical = 8.dp),
                )
            }

            when {
                loading && total == 0 ->
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
                total == 0 ->
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Column(
                            horizontalAlignment = Alignment.CenterHorizontally,
                            verticalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            Text("No reminders scheduled", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                            Text("Tap the button below to schedule your first follow-up alert.", color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
                            Button(
                                onClick = { showCreateDialog = true },
                                colors = ButtonDefaults.buttonColors(containerColor = DentalColors.Teal600),
                                shape = RoundedCornerShape(10.dp)
                            ) {
                                Text("+ Schedule Reminder", fontWeight = FontWeight.Bold)
                            }
                        }
                    }
                else -> LazyColumn(
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                    contentPadding = PaddingValues(vertical = 10.dp),
                ) {
                    SECTION_ORDER.forEach { bucket ->
                        val rows = grouped[bucket].orEmpty()
                        if (rows.isNotEmpty()) {
                            item(key = "hdr-$bucket") {
                                Text(
                                    "${bucket.label()} · ${rows.size}",
                                    style = MaterialTheme.typography.titleSmall,
                                    fontWeight = FontWeight.Bold,
                                    color = if (bucket == ReminderBucket.OVERDUE) MaterialTheme.colorScheme.error
                                    else MaterialTheme.colorScheme.primary,
                                    modifier = Modifier.padding(top = 8.dp, bottom = 2.dp),
                                )
                            }
                            items(rows, key = { it.id }) { r ->
                                ReminderRow(
                                    r,
                                    onOpenLead = onOpenLead,
                                    onSnooze = { vm.snooze(r, it) },
                                    onComplete = { vm.complete(r) },
                                )
                            }
                        }
                    }
                    item { Box(Modifier.padding(bottom = 60.dp)) {} }
                }
            }
        }
    }

    if (showCreateDialog) {
        CreateReminderDialog(
            onDismiss = { showCreateDialog = false },
            onSave = { title, note, preset, priority ->
                vm.createReminder(title, note, preset, priority) {
                    showCreateDialog = false
                }
            }
        )
    }
}

@Composable
private fun CreateReminderDialog(
    onDismiss: () -> Unit,
    onSave: (title: String, note: String?, preset: String, priority: String) -> Unit
) {
    var title by remember { mutableStateOf("") }
    var notes by remember { mutableStateOf("") }
    var selectedPreset by remember { mutableStateOf("Tomorrow 10am") }
    var selectedPriority by remember { mutableStateOf("Medium") }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Schedule Follow-up Reminder", fontWeight = FontWeight.Bold) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                OutlinedTextField(
                    value = title,
                    onValueChange = { title = it },
                    label = { Text("Reminder Title / Contact *") },
                    placeholder = { Text("e.g. Call Rajesh for dental crown quote") },
                    singleLine = true,
                    shape = RoundedCornerShape(10.dp),
                    modifier = Modifier.fillMaxWidth()
                )

                OutlinedTextField(
                    value = notes,
                    onValueChange = { notes = it },
                    label = { Text("Notes / Remarks (Optional)") },
                    placeholder = { Text("Discuss pricing and confirm appointment date") },
                    shape = RoundedCornerShape(10.dp),
                    minLines = 2,
                    modifier = Modifier.fillMaxWidth()
                )

                Text("Remind Me When", style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold)
                LazyRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    items(REMINDER_PRESETS) { p ->
                        val isSelected = selectedPreset == p
                        FilterChip(
                            selected = isSelected,
                            onClick = { selectedPreset = p },
                            label = { Text(p, fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal) }
                        )
                    }
                }

                Text("Priority Level", style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold)
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    PRIORITIES.forEach { p ->
                        val isSelected = selectedPriority == p
                        FilterChip(
                            selected = isSelected,
                            onClick = { selectedPriority = p },
                            label = { Text(p, fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal) }
                        )
                    }
                }
            }
        },
        confirmButton = {
            Button(
                onClick = { onSave(title, notes.ifBlank { null }, selectedPreset, selectedPriority) },
                enabled = title.isNotBlank(),
                colors = ButtonDefaults.buttonColors(containerColor = DentalColors.Teal600),
                shape = RoundedCornerShape(8.dp)
            ) {
                Text("Set Reminder", fontWeight = FontWeight.Bold)
            }
        },
        dismissButton = {
            OutlinedButton(onClick = onDismiss, shape = RoundedCornerShape(8.dp)) {
                Text("Cancel")
            }
        }
    )
}

private val TIME_FMT = SimpleDateFormat("EEE d MMM · h:mm a", Locale.getDefault())

@Composable
private fun ReminderRow(
    r: Reminder,
    onOpenLead: (String) -> Unit,
    onSnooze: (SnoozeOption) -> Unit,
    onComplete: () -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        border = CardDefaults.outlinedCardBorder().copy(
            brush = SolidColor(MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.6f))
        )
    ) {
        Column(Modifier.padding(14.dp).fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    r.title,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    color = if (r.isDone) MaterialTheme.colorScheme.onSurfaceVariant else MaterialTheme.colorScheme.onSurface,
                    modifier = Modifier.weight(1f)
                )

                // Priority Badge
                val (pColor, pBg) = when (r.priority.lowercase()) {
                    "urgent", "high" -> MaterialTheme.colorScheme.error to MaterialTheme.colorScheme.errorContainer.copy(alpha = 0.5f)
                    "medium" -> DentalColors.StatusCrown to DentalColors.StatusCrownBg
                    else -> MaterialTheme.colorScheme.onSurfaceVariant to MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f)
                }

                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(6.dp))
                        .background(pBg)
                        .padding(horizontal = 8.dp, vertical = 3.dp)
                ) {
                    Text(
                        r.priority,
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.Bold,
                        color = pColor
                    )
                }
            }

            r.description?.takeIf { it.isNotBlank() }?.let {
                Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 2)
            }

            Text(
                "⏰ ${TIME_FMT.format(Date(r.remindAtMillis))}",
                style = MaterialTheme.typography.labelSmall,
                fontWeight = FontWeight.Medium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )

            if (!r.isDone) {
                Row(
                    Modifier.fillMaxWidth().padding(top = 4.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    SnoozeButton(onSnooze)
                    Button(
                        onClick = onComplete,
                        shape = RoundedCornerShape(8.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = DentalColors.Teal600),
                        modifier = Modifier.height(34.dp)
                    ) {
                        Text("✓ Done", style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold)
                    }
                    r.leadId?.let { id ->
                        OutlinedButton(
                            onClick = { onOpenLead(id) },
                            shape = RoundedCornerShape(8.dp),
                            modifier = Modifier.height(34.dp)
                        ) {
                            Text("Open Lead ➔", style = MaterialTheme.typography.labelSmall)
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun SnoozeButton(onSnooze: (SnoozeOption) -> Unit) {
    var open by remember { mutableStateOf(false) }
    Box {
        OutlinedButton(
            onClick = { open = true },
            shape = RoundedCornerShape(8.dp),
            modifier = Modifier.height(34.dp)
        ) {
            Text("⏱️ Snooze", style = MaterialTheme.typography.labelSmall)
        }
        DropdownMenu(expanded = open, onDismissRequest = { open = false }) {
            SnoozeOption.entries.forEach { opt ->
                DropdownMenuItem(
                    text = { Text(opt.label) },
                    onClick = { open = false; onSnooze(opt) },
                )
            }
        }
    }
}
