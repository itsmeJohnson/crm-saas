package com.crm.mobile.feature.reports

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
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

@HiltViewModel
class ReportsViewModel @Inject constructor(private val repo: ReportsRepository) : ViewModel() {
    private val _loading = MutableStateFlow(true)
    val loading: StateFlow<Boolean> = _loading.asStateFlow()
    private val _offline = MutableStateFlow(false)
    val offline: StateFlow<Boolean> = _offline.asStateFlow()

    val bundle: StateFlow<ReportsBundle?> = repo.reports
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), null)

    init { refresh() }

    fun refresh() {
        _loading.value = true
        viewModelScope.launch { _offline.value = !repo.refresh(); _loading.value = false }
    }
}

private val TABS = listOf("Overview", "Tasks", "Comms")

@Composable
fun ReportsScreen(vm: ReportsViewModel = hiltViewModel()) {
    val loading by vm.loading.collectAsStateWithLifecycle()
    val offline by vm.offline.collectAsStateWithLifecycle()
    val bundle by vm.bundle.collectAsStateWithLifecycle()
    var tab by remember { mutableIntStateOf(0) }

    Column(Modifier.fillMaxSize()) {
        TabRow(selectedTabIndex = tab) {
            TABS.forEachIndexed { i, title ->
                Tab(selected = tab == i, onClick = { tab = i }, text = { Text(title) })
            }
        }
        if (offline) Text(
            "Offline — showing cached reports", color = MaterialTheme.colorScheme.error,
            style = MaterialTheme.typography.labelMedium,
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp),
        )
        when {
            loading && bundle == null ->
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
            bundle == null ->
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { Text("No report data") }
            else -> Column(
                Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(12.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                when (tab) {
                    0 -> OverviewTab(bundle!!.dashboard)
                    1 -> TasksTab(bundle!!.tasks)
                    else -> CommsTab(bundle!!.comm)
                }
            }
        }
    }
}

// ---- Tabs ----

@Composable
private fun OverviewTab(d: DashSummaryDto?) {
    if (d == null) { EmptyTab(); return }
    StatGrid(
        listOfNotNull(
            "Leads" to d.total_leads.toString(),
            "Contacts" to d.contacts_count.toString(),
            "Companies" to d.companies_count.toString(),
            "Activities" to d.activities_count.toString(),
            d.conversion_rate?.let { "Conversion" to pct(it) },
        ),
    )
    BarCard("Leads by status", d.leads_by_status.map { LabelCount(it.key, it.value) })
}

@Composable
private fun TasksTab(t: TaskReportDto?) {
    if (t == null) { EmptyTab(); return }
    StatGrid(
        listOf(
            "Total" to t.total.toString(),
            "Open" to t.open.toString(),
            "Completed" to t.completed.toString(),
            "Overdue" to t.overdue.toString(),
            "Due today" to t.due_today.toString(),
            "Completion" to pct(t.completion_rate),
        ),
    )
    BarCard("By priority", t.by_priority)
    BarCard("By status", t.by_status)
}

@Composable
private fun CommsTab(c: CommOverviewDto?) {
    if (c == null) { EmptyTab(); return }
    StatGrid(
        listOf(
            "Total" to c.total.toString(),
            "Outbound" to c.outbound.toString(),
            "Inbound" to c.inbound.toString(),
            "Delivered" to c.delivered.toString(),
            "Failed" to c.failed.toString(),
            "Delivery" to pct(c.delivery_rate),
        ),
    )
    BarCard("By channel", c.by_channel)
}

@Composable
private fun EmptyTab() {
    Text("Not available for your role", style = MaterialTheme.typography.bodyMedium,
        color = MaterialTheme.colorScheme.onSurfaceVariant)
}

// ---- Reusable pieces ----

/** Renders KPI stats two per row (last cell padded when odd). */
@Composable
private fun StatGrid(stats: List<Pair<String, String>>) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        stats.chunked(2).forEach { row ->
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                row.forEach { (label, value) -> StatCard(label, value, Modifier.weight(1f)) }
                if (row.size == 1) Spacer(Modifier.weight(1f))
            }
        }
    }
}

@Composable
private fun StatCard(label: String, value: String, modifier: Modifier = Modifier) {
    Card(modifier) {
        Column(Modifier.fillMaxWidth().padding(14.dp)) {
            Text(value, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.SemiBold)
            Text(label, style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

/** A horizontal bar chart drawn with plain Compose (no chart library). */
@Composable
private fun BarCard(title: String, buckets: List<LabelCount>) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.fillMaxWidth().padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(title, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
            if (buckets.isEmpty()) {
                Text("No data", style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
            } else {
                val max = (buckets.maxOfOrNull { it.count } ?: 1).coerceAtLeast(1)
                buckets.forEach { b -> BarRow(b.label, b.count, max) }
            }
        }
    }
}

@Composable
private fun BarRow(label: String, count: Int, max: Int) {
    Row(verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(label, style = MaterialTheme.typography.labelSmall,
            modifier = Modifier.width(84.dp), maxLines = 1)
        Box(
            Modifier.weight(1f).height(18.dp).clip(RoundedCornerShape(4.dp))
                .background(MaterialTheme.colorScheme.surfaceVariant),
        ) {
            Box(
                Modifier.fillMaxWidth(count.toFloat() / max).fillMaxHeight()
                    .clip(RoundedCornerShape(4.dp))
                    .background(MaterialTheme.colorScheme.primary),
            )
        }
        Text(count.toString(), style = MaterialTheme.typography.labelSmall,
            modifier = Modifier.width(32.dp))
    }
}

/** Formats a backend rate (already 0–100) as a percentage string. */
private fun pct(v: Double): String = "${(v * 10).toInt() / 10.0}%"
