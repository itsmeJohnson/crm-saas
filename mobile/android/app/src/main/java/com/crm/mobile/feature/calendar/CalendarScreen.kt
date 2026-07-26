package com.crm.mobile.feature.calendar

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
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
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import java.time.DayOfWeek
import java.time.Instant
import java.time.LocalDate
import java.time.YearMonth
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.time.temporal.TemporalAdjusters
import javax.inject.Inject

enum class CalView { DAY, WEEK, MONTH }

data class DaySection(val date: LocalDate, val items: List<CalItem>)

private val ZONE: ZoneId = ZoneId.systemDefault()
private fun Long.toLocalDate(): LocalDate = Instant.ofEpochMilli(this).atZone(ZONE).toLocalDate()
private fun LocalDate.startIso(): String = atStartOfDay(ZONE).toInstant().toString()

@HiltViewModel
class CalendarViewModel @Inject constructor(
    private val repo: CalendarRepository,
) : ViewModel() {

    private val _month = MutableStateFlow(YearMonth.now(ZONE))
    val month: StateFlow<YearMonth> = _month.asStateFlow()

    private val _view = MutableStateFlow(CalView.MONTH)
    val view: StateFlow<CalView> = _view.asStateFlow()

    private val _loading = MutableStateFlow(true)
    val loading: StateFlow<Boolean> = _loading.asStateFlow()

    private val _offline = MutableStateFlow(false)
    val offline: StateFlow<Boolean> = _offline.asStateFlow()

    val sections: StateFlow<List<DaySection>> =
        combine(repo.items, _view, _month) { items, view, month ->
            val today = LocalDate.now(ZONE)
            val weekStart = today.with(TemporalAdjusters.previousOrSame(DayOfWeek.MONDAY))
            val weekEnd = weekStart.plusDays(7)
            // Each branch is a single-expression predicate — a `when` branch
            // written as `-> { a; b }` would be parsed as a lambda, not a block.
            val range: (LocalDate) -> Boolean = when (view) {
                CalView.MONTH -> { d -> YearMonth.from(d) == month }
                CalView.WEEK -> { d -> !d.isBefore(weekStart) && d.isBefore(weekEnd) }
                CalView.DAY -> { d -> d == today }
            }
            items.groupBy { it.startMillis.toLocalDate() }
                .filterKeys(range)
                .toSortedMap()
                .map { (date, dayItems) -> DaySection(date, dayItems.sortedBy { it.startMillis }) }
        }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    init { refresh() }

    fun refresh() {
        _loading.value = true
        viewModelScope.launch {
            val m = _month.value
            val from = m.atDay(1).startIso()
            val to = m.plusMonths(1).atDay(1).startIso()
            _offline.value = !repo.refresh(from, to)
            _loading.value = false
        }
    }

    fun selectView(v: CalView) { _view.value = v }
    fun prevMonth() { _month.value = _month.value.minusMonths(1); _view.value = CalView.MONTH; refresh() }
    fun nextMonth() { _month.value = _month.value.plusMonths(1); _view.value = CalView.MONTH; refresh() }
}

private val MONTH_FMT = DateTimeFormatter.ofPattern("MMMM yyyy")
private val DAY_FMT = DateTimeFormatter.ofPattern("EEE, MMM d")
private val TIME_FMT = DateTimeFormatter.ofPattern("h:mm a")

@Composable
fun CalendarScreen(vm: CalendarViewModel = hiltViewModel()) {
    val month by vm.month.collectAsStateWithLifecycle()
    val view by vm.view.collectAsStateWithLifecycle()
    val loading by vm.loading.collectAsStateWithLifecycle()
    val offline by vm.offline.collectAsStateWithLifecycle()
    val sections by vm.sections.collectAsStateWithLifecycle()

    Column(Modifier.fillMaxSize().padding(horizontal = 12.dp)) {
        if (offline) {
            Text("Offline — showing last synced calendar", color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.labelMedium, modifier = Modifier.padding(vertical = 8.dp))
        }
        Row(Modifier.fillMaxWidth().padding(top = 8.dp), verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween) {
            TextButton(onClick = vm::prevMonth) { Text("‹") }
            Text(month.format(MONTH_FMT), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            TextButton(onClick = vm::nextMonth) { Text("›") }
        }
        Row(Modifier.fillMaxWidth().padding(vertical = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            CalView.values().forEach { v ->
                FilterChip(selected = view == v, onClick = { vm.selectView(v) },
                    label = { Text(v.name.lowercase().replaceFirstChar { it.uppercase() }) })
            }
        }

        when {
            loading && sections.isEmpty() ->
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
            sections.isEmpty() ->
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Text("No events in this period", style = MaterialTheme.typography.bodyMedium)
                }
            else -> LazyColumn(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                sections.forEach { section ->
                    item(key = "h-${section.date}") {
                        Text(section.date.format(DAY_FMT), style = MaterialTheme.typography.labelLarge,
                            fontWeight = FontWeight.SemiBold, modifier = Modifier.padding(top = 10.dp, bottom = 2.dp))
                    }
                    items(section.items.size, key = { section.items[it].id }) { i -> EventRow(section.items[i]) }
                }
            }
        }
    }
}

@Composable
private fun EventRow(item: CalItem) {
    Card(Modifier.fillMaxWidth()) {
        Row(Modifier.padding(12.dp).fillMaxWidth(), verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween) {
            Column(Modifier.padding(end = 8.dp)) {
                Text(item.title, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Medium)
                val time = if (item.allDay) "All day"
                    else Instant.ofEpochMilli(item.startMillis).atZone(ZONE).toLocalTime().format(TIME_FMT)
                Text("${item.type} · $time", style = MaterialTheme.typography.labelSmall)
            }
            if (item.hasReminder) Text("🔔", style = MaterialTheme.typography.labelMedium)
        }
    }
}
