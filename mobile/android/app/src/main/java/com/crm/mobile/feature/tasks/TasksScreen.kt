package com.crm.mobile.feature.tasks

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
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
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import java.time.LocalDate
import java.time.ZoneId
import java.util.Date
import javax.inject.Inject

@HiltViewModel
class TasksViewModel @Inject constructor(
    private val repo: TaskRepository,
) : ViewModel() {

    private val _tab = MutableStateFlow(TaskBucket.TODAY)
    val tab: StateFlow<TaskBucket> = _tab.asStateFlow()

    private val _query = MutableStateFlow("")
    val query: StateFlow<String> = _query.asStateFlow()

    private val _loading = MutableStateFlow(true)
    val loading: StateFlow<Boolean> = _loading.asStateFlow()

    private val _offline = MutableStateFlow(false)
    val offline: StateFlow<Boolean> = _offline.asStateFlow()

    val visible: StateFlow<List<Task>> =
        combine(repo.tasks, _tab, _query) { list, tab, q ->
            val (start, end) = todayBounds()
            list.filter { it.bucket(start, end) == tab }
                .filter { q.isBlank() || it.title.contains(q, ignoreCase = true) }
        }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    init { refresh() }

    fun refresh() {
        _loading.value = true
        viewModelScope.launch {
            _offline.value = !repo.refresh()
            _loading.value = false
        }
    }

    fun selectTab(b: TaskBucket) { _tab.value = b }
    fun setQuery(q: String) { _query.value = q }
    fun complete(id: String) { viewModelScope.launch { if (!repo.complete(id)) _offline.value = true } }

    private fun todayBounds(): Pair<Long, Long> {
        val zone = ZoneId.systemDefault()
        val start = LocalDate.now(zone).atStartOfDay(zone).toInstant().toEpochMilli()
        val end = LocalDate.now(zone).plusDays(1).atStartOfDay(zone).toInstant().toEpochMilli()
        return start to end
    }
}

private val TABS = listOf(
    TaskBucket.TODAY to "Today",
    TaskBucket.UPCOMING to "Upcoming",
    TaskBucket.OVERDUE to "Overdue",
    TaskBucket.COMPLETED to "Completed",
)

@Composable
fun TasksScreen(vm: TasksViewModel = hiltViewModel()) {
    val tab by vm.tab.collectAsStateWithLifecycle()
    val query by vm.query.collectAsStateWithLifecycle()
    val loading by vm.loading.collectAsStateWithLifecycle()
    val offline by vm.offline.collectAsStateWithLifecycle()
    val tasks by vm.visible.collectAsStateWithLifecycle()

    Column(Modifier.fillMaxSize().padding(horizontal = 14.dp)) {
        if (offline) {
            Text(
                "⚠️ Offline — showing cached tasks",
                color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.labelSmall,
                fontWeight = FontWeight.Medium,
                modifier = Modifier.padding(vertical = 6.dp)
            )
        }

        OutlinedTextField(
            value = query,
            onValueChange = vm::setQuery,
            label = { Text("Search tasks and to-dos") },
            trailingIcon = {
                IconButton(onClick = vm::refresh) {
                    Text("🔄", fontSize = 16.sp)
                }
            },
            singleLine = true,
            shape = RoundedCornerShape(12.dp),
            modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
        )

        Row(
            modifier = Modifier.fillMaxWidth().padding(vertical = 10.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            TABS.forEach { (bucket, label) ->
                val isSelected = tab == bucket
                FilterChip(
                    selected = isSelected,
                    onClick = { vm.selectTab(bucket) },
                    label = { Text(label, fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal) }
                )
            }
        }

        when {
            loading && tasks.isEmpty() ->
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
            tasks.isEmpty() ->
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text("No tasks in this section", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        OutlinedButton(onClick = vm::refresh) {
                            Text("Refresh Tasks")
                        }
                    }
                }
            else -> LazyColumn(
                modifier = Modifier.fillMaxSize(),
                verticalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                items(tasks, key = { it.id }) { t -> TaskRow(t, onComplete = { vm.complete(t.id) }) }
                item { Box(Modifier.padding(bottom = 16.dp)) {} }
            }
        }
    }
}

@Composable
private fun TaskRow(t: Task, onComplete: () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(14.dp),
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
                    t.title,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    color = if (t.isDone) MaterialTheme.colorScheme.onSurfaceVariant else MaterialTheme.colorScheme.onSurface,
                    modifier = Modifier.weight(1f)
                )

                // Priority Badge
                val (pColor, pBg) = when (t.priority.lowercase()) {
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
                        t.priority,
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.Bold,
                        color = pColor
                    )
                }
            }

            t.description?.takeIf { it.isNotBlank() }?.let {
                Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 2)
            }

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    t.dueAtMillis?.let { "⏰ Due ${Date(it).toString().take(16)}" } ?: "No deadline",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )

                if (!t.isDone) {
                    Button(
                        onClick = onComplete,
                        shape = RoundedCornerShape(8.dp),
                        colors = ButtonDefaults.buttonColors(
                            containerColor = DentalColors.Teal600
                        ),
                        modifier = Modifier.height(34.dp)
                    ) {
                        Text("✓ Mark Done", style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold)
                    }
                } else {
                    Text(
                        "✓ Completed",
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.Bold,
                        color = DentalColors.StatusHealthy
                    )
                }
            }
        }
    }
}
