package com.crm.mobile.feature.dashboard

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
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
import kotlinx.coroutines.launch
import javax.inject.Inject

data class DashboardUiState(val loading: Boolean = false, val offline: Boolean = false)

@HiltViewModel
class DashboardViewModel @Inject constructor(
    private val repo: DashboardRepository,
) : ViewModel() {

    val summary: StateFlow<DashboardSummary?> =
        repo.summary.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), null)

    private val _ui = MutableStateFlow(DashboardUiState(loading = true))
    val ui: StateFlow<DashboardUiState> = _ui.asStateFlow()

    init { refresh() }

    fun refresh() {
        _ui.value = _ui.value.copy(loading = true)
        viewModelScope.launch {
            val ok = repo.refresh()
            _ui.value = DashboardUiState(loading = false, offline = !ok)
        }
    }

    fun toggleClock(currentlyOnline: Boolean) {
        viewModelScope.launch {
            val ok = if (currentlyOnline) repo.clockOut() else repo.clockIn()
            if (!ok) _ui.value = _ui.value.copy(offline = true)
        }
    }
}

@Composable
fun DashboardScreen(
    onOpenLeads: () -> Unit = {},
    vm: DashboardViewModel = hiltViewModel(),
) {
    val summary by vm.summary.collectAsStateWithLifecycle()
    val ui by vm.ui.collectAsStateWithLifecycle()
    val s = summary

    when {
        s == null && ui.loading -> LoadingState()
        s == null -> EmptyState(onRetry = vm::refresh)
        else -> LazyColumn(
            modifier = Modifier.fillMaxSize().padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            if (ui.offline) item { OfflineBanner() }
            item { HeroCard(s, onToggleClock = { vm.toggleClock(s.isOnline) }) }
            item { StatGrid(s) }
            item { TargetProgress(s) }
            item { QuickActions(onOpenLeads = onOpenLeads) }
            item {
                Text("Recent activity", style = MaterialTheme.typography.titleMedium,
                    modifier = Modifier.padding(top = 4.dp))
            }
            if (s.recent.isEmpty()) {
                item { Text("Nothing yet today.", style = MaterialTheme.typography.bodySmall) }
            } else {
                items(s.recent, key = { it.id }) { a -> ActivityRow(a) }
            }
            item { Box(Modifier.padding(bottom = 24.dp)) {} }
        }
    }
}

@Composable
private fun HeroCard(s: DashboardSummary, onToggleClock: () -> Unit) {
    Card(modifier = Modifier.fillMaxWidth().padding(top = 12.dp)) {
        Column(Modifier.padding(18.dp)) {
            Text(s.employeeName, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
            val status = if (s.isOnline) "On the clock" else "Off the clock"
            Text(status, color = if (s.isOnline) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant,
                style = MaterialTheme.typography.labelLarge)
            Text("Working today: ${s.workingMinutes / 60}h ${s.workingMinutes % 60}m",
                style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(top = 6.dp))
            Button(onClick = onToggleClock, modifier = Modifier.padding(top = 12.dp)) {
                Text(if (s.isOnline) "Check out" else "Check in")
            }
        }
    }
}

@Composable
private fun StatGrid(s: DashboardSummary) {
    val stats = listOf(
        "Calls today" to s.callsToday,
        "Today's follow-ups" to s.todaysFollowUps,
        "Overdue follow-ups" to s.overdueFollowUps,
        "Interested leads" to s.interestedLeads,
        "Meetings today" to s.meetingsToday,
        "Tasks pending" to s.tasksPending,
        "Overdue tasks" to s.overdueTasks,
    )
    // Plain Row/Column layout (no nested lazy scroll) so it composes inside the
    // parent LazyColumn without a bounded-height hack.
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        stats.chunked(2).forEach { pair ->
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                pair.forEach { (label, value) ->
                    Box(Modifier.weight(1f)) { StatTile(label, value) }
                }
                if (pair.size == 1) Box(Modifier.weight(1f)) {}
            }
        }
    }
}

@Composable
private fun StatTile(label: String, value: Int) {
    Card(Modifier.fillMaxWidth().semantics { contentDescription = "$label: $value" }) {
        Column(Modifier.padding(14.dp)) {
            Text("$value", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
            Text(label, style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
private fun TargetProgress(s: DashboardSummary) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp)) {
            Text("Conversion progress", style = MaterialTheme.typography.titleSmall)
            Text("${s.leadsConverted} of ${s.leadsTotal} leads", style = MaterialTheme.typography.bodySmall)
            LinearProgressIndicator(
                progress = { s.conversionProgress },
                modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
            )
        }
    }
}

@Composable
private fun QuickActions(onOpenLeads: () -> Unit) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        OutlinedButton(onClick = onOpenLeads, modifier = Modifier.fillMaxWidth()) { Text("My leads") }
    }
}

@Composable
private fun ActivityRow(a: RecentActivity) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp)) {
            Text(a.subject, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Medium)
            Text("${a.type}${a.status?.let { " · $it" } ?: ""}", style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
private fun OfflineBanner() {
    Text(
        "Offline — showing your last synced dashboard",
        color = MaterialTheme.colorScheme.error,
        style = MaterialTheme.typography.labelMedium,
        modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
    )
}

@Composable
private fun LoadingState() {
    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
}

@Composable
private fun EmptyState(onRetry: () -> Unit) {
    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text("Couldn't load your dashboard", style = MaterialTheme.typography.titleMedium)
            Button(onClick = onRetry, modifier = Modifier.padding(top = 12.dp)) { Text("Retry") }
        }
    }
}
