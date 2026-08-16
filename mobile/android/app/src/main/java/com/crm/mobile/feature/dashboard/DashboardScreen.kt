package com.crm.mobile.feature.dashboard

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
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
                Text(
                    "Recent Activity",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier.padding(top = 4.dp)
                )
            }
            if (s.recent.isEmpty()) {
                item { Text("No logged activity yet today.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
            } else {
                items(s.recent, key = { it.id }) { a -> ActivityRow(a) }
            }
            item { Box(Modifier.padding(bottom = 24.dp)) {} }
        }
    }
}

@Composable
private fun HeroCard(s: DashboardSummary, onToggleClock: () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        border = CardDefaults.outlinedCardBorder().copy(
            brush = SolidColor(MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.6f))
        )
    ) {
        Column(Modifier.padding(18.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    val (avatarFg, avatarBg) = DentalColors.getAvatarColor(s.employeeName)
                    Box(
                        modifier = Modifier
                            .size(44.dp)
                            .clip(CircleShape)
                            .background(avatarBg),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            s.employeeName.take(1).uppercase().ifBlank { "U" },
                            color = avatarFg,
                            fontWeight = FontWeight.Bold,
                            style = MaterialTheme.typography.titleMedium
                        )
                    }
                    Column {
                        Text(s.employeeName, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(6.dp)
                        ) {
                            Box(
                                modifier = Modifier
                                    .size(8.dp)
                                    .clip(CircleShape)
                                    .background(
                                        if (s.isOnline) DentalColors.StatusHealthy else DentalColors.Slate400
                                    )
                            )
                            Text(
                                if (s.isOnline) "Checked In" else "Checked Out",
                                color = if (s.isOnline) DentalColors.StatusHealthy else MaterialTheme.colorScheme.onSurfaceVariant,
                                style = MaterialTheme.typography.labelSmall,
                                fontWeight = FontWeight.SemiBold
                            )
                        }
                    }
                }

                // Working timer pill
                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(12.dp))
                        .background(DentalColors.Teal50)
                        .padding(horizontal = 10.dp, vertical = 6.dp)
                ) {
                    Text(
                        "⏱️ ${s.workingMinutes / 60}h ${s.workingMinutes % 60}m",
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.Bold,
                        color = DentalColors.Teal900
                    )
                }
            }

            Button(
                onClick = onToggleClock,
                shape = RoundedCornerShape(12.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = if (s.isOnline) MaterialTheme.colorScheme.error else DentalColors.Teal600
                ),
                modifier = Modifier.fillMaxWidth().padding(top = 16.dp)
            ) {
                Text(
                    if (s.isOnline) "Clock Out for Today" else "Clock In to Practice",
                    fontWeight = FontWeight.Bold,
                    style = MaterialTheme.typography.labelLarge
                )
            }
        }
    }
}

private data class StatItem(val label: String, val value: Int, val icon: String, val isWarning: Boolean = false)

@Composable
private fun StatGrid(s: DashboardSummary) {
    val stats = listOf(
        StatItem("Calls Today", s.callsToday, "📞"),
        StatItem("Today's Follow-ups", s.todaysFollowUps, "🎯"),
        StatItem("Overdue Follow-ups", s.overdueFollowUps, "⚠️", isWarning = s.overdueFollowUps > 0),
        StatItem("Interested Leads", s.interestedLeads, "⭐"),
        StatItem("Meetings Today", s.meetingsToday, "📅"),
        StatItem("Pending Tasks", s.tasksPending, "📋"),
        StatItem("Overdue Tasks", s.overdueTasks, "🚨", isWarning = s.overdueTasks > 0),
    )

    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Text("Daily Operations & KPIs", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
        stats.chunked(2).forEach { pair ->
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                pair.forEach { item ->
                    Box(Modifier.weight(1f)) { StatTile(item) }
                }
                if (pair.size == 1) Box(Modifier.weight(1f)) {}
            }
        }
    }
}

@Composable
private fun StatTile(item: StatItem) {
    Card(
        modifier = Modifier.fillMaxWidth().semantics { contentDescription = "${item.label}: ${item.value}" },
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(
            containerColor = if (item.isWarning) MaterialTheme.colorScheme.errorContainer.copy(alpha = 0.35f)
            else MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f)
        )
    ) {
        Row(
            modifier = Modifier.padding(14.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            Text(item.icon, fontSize = 22.sp)
            Column {
                Text(
                    "${item.value}",
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.Bold,
                    color = if (item.isWarning) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurface
                )
                Text(
                    item.label,
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}

@Composable
private fun TargetProgress(s: DashboardSummary) {
    val percentage = (s.conversionProgress * 100).toInt()
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        border = CardDefaults.outlinedCardBorder().copy(
            brush = SolidColor(MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.6f))
        )
    ) {
        Column(Modifier.padding(16.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Text("Lead Conversion Performance", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
                    Text("${s.leadsConverted} converted out of ${s.leadsTotal} total leads", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(10.dp))
                        .background(DentalColors.Teal100)
                        .padding(horizontal = 8.dp, vertical = 4.dp)
                ) {
                    Text("$percentage%", style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold, color = DentalColors.Teal900)
                }
            }
            LinearProgressIndicator(
                progress = { s.conversionProgress },
                color = DentalColors.Teal600,
                trackColor = DentalColors.Teal100,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 10.dp)
                    .height(8.dp)
                    .clip(RoundedCornerShape(4.dp))
            )
        }
    }
}

@Composable
private fun QuickActions(onOpenLeads: () -> Unit) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        OutlinedButton(
            onClick = onOpenLeads,
            shape = RoundedCornerShape(12.dp),
            modifier = Modifier.fillMaxWidth().height(46.dp)
        ) {
            Text("🎯 Open Leads & Pipeline", fontWeight = FontWeight.Bold)
        }
    }
}

@Composable
private fun ActivityRow(a: RecentActivity) {
    val icon = when (a.type.lowercase()) {
        "call" -> "📞"
        "meeting" -> "📅"
        "email" -> "✉️"
        "whatsapp" -> "💬"
        else -> "📝"
    }
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.35f))
    ) {
        Row(
            modifier = Modifier.padding(12.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Box(
                modifier = Modifier
                    .size(36.dp)
                    .clip(RoundedCornerShape(10.dp))
                    .background(DentalColors.Teal100),
                contentAlignment = Alignment.Center
            ) {
                Text(icon, fontSize = 16.sp)
            }
            Column(modifier = Modifier.weight(1f)) {
                Text(a.subject, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.SemiBold)
                Text(
                    "${a.type}${a.status?.let { " · $it" } ?: ""}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}

@Composable
private fun OfflineBanner() {
    Card(
        shape = RoundedCornerShape(10.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer.copy(alpha = 0.5f)),
        modifier = Modifier.fillMaxWidth().padding(top = 10.dp)
    ) {
        Text(
            "⚠️ Offline — displaying last cached practice snapshot",
            color = MaterialTheme.colorScheme.error,
            style = MaterialTheme.typography.labelSmall,
            fontWeight = FontWeight.Medium,
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
        )
    }
}

@Composable
private fun LoadingState() {
    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
}

@Composable
private fun EmptyState(onRetry: () -> Unit) {
    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text("Couldn't load dashboard", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            Button(onClick = onRetry, shape = RoundedCornerShape(10.dp)) { Text("Retry") }
        }
    }
}
