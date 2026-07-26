package com.crm.mobile.feature.reminders

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
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
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.time.LocalDate
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

@Composable
fun ReminderScreen(onOpenLead: (String) -> Unit, vm: ReminderViewModel = hiltViewModel()) {
    val loading by vm.loading.collectAsStateWithLifecycle()
    val offline by vm.offline.collectAsStateWithLifecycle()
    val grouped by vm.grouped.collectAsStateWithLifecycle()
    val total = grouped.values.sumOf { it.size }

    Column(Modifier.fillMaxSize().padding(horizontal = 12.dp)) {
        if (offline) Text(
            "Offline — showing cached reminders", color = MaterialTheme.colorScheme.error,
            style = MaterialTheme.typography.labelMedium, modifier = Modifier.padding(vertical = 8.dp),
        )
        when {
            loading && total == 0 ->
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
            total == 0 ->
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { Text("No reminders") }
            else -> LazyColumn(
                verticalArrangement = Arrangement.spacedBy(8.dp),
                contentPadding = PaddingValues(vertical = 8.dp),
            ) {
                SECTION_ORDER.forEach { bucket ->
                    val rows = grouped[bucket].orEmpty()
                    if (rows.isNotEmpty()) {
                        item(key = "hdr-$bucket") {
                            Text(
                                "${bucket.label()} · ${rows.size}",
                                style = MaterialTheme.typography.titleSmall,
                                fontWeight = FontWeight.SemiBold,
                                color = if (bucket == ReminderBucket.OVERDUE) MaterialTheme.colorScheme.error
                                else MaterialTheme.colorScheme.onSurfaceVariant,
                                modifier = Modifier.padding(top = 6.dp),
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
            }
        }
    }
}

private val TIME_FMT = SimpleDateFormat("EEE d MMM · h:mm a", Locale.getDefault())

@Composable
private fun ReminderRow(
    r: Reminder,
    onOpenLead: (String) -> Unit,
    onSnooze: (SnoozeOption) -> Unit,
    onComplete: () -> Unit,
) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp).fillMaxWidth()) {
            Text(r.title, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Medium)
            r.description?.takeIf { it.isNotBlank() }?.let {
                Text(it, style = MaterialTheme.typography.bodySmall, maxLines = 2)
            }
            val meta = listOfNotNull(TIME_FMT.format(Date(r.remindAtMillis)), r.priority)
                .joinToString(" · ")
            Text(meta, style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant)

            if (!r.isDone) {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                    SnoozeButton(onSnooze)
                    TextButton(onClick = onComplete) { Text("Done") }
                    r.leadId?.let { id -> TextButton(onClick = { onOpenLead(id) }) { Text("Lead") } }
                }
            }
        }
    }
}

@Composable
private fun SnoozeButton(onSnooze: (SnoozeOption) -> Unit) {
    var open by remember { mutableStateOf(false) }
    Box {
        TextButton(onClick = { open = true }) { Text("Snooze") }
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
