package com.crm.mobile.feature.tasks

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
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

    Column(Modifier.fillMaxSize().padding(horizontal = 12.dp)) {
        if (offline) {
            Text("Offline — showing cached tasks", color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.labelMedium, modifier = Modifier.padding(vertical = 8.dp))
        }
        OutlinedTextField(
            value = query, onValueChange = vm::setQuery, label = { Text("Search tasks") },
            singleLine = true, modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
        )
        Row(Modifier.fillMaxWidth().padding(vertical = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            TABS.forEach { (bucket, label) ->
                FilterChip(selected = tab == bucket, onClick = { vm.selectTab(bucket) }, label = { Text(label) })
            }
        }

        when {
            loading && tasks.isEmpty() ->
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
            tasks.isEmpty() ->
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Text("Nothing here", style = MaterialTheme.typography.bodyMedium)
                }
            else -> LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                items(tasks, key = { it.id }) { t -> TaskRow(t, onComplete = { vm.complete(t.id) }) }
            }
        }
    }
}

@Composable
private fun TaskRow(t: Task, onComplete: () -> Unit) {
    androidx.compose.material3.Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp)) {
            Text(t.title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Medium)
            t.description?.takeIf { it.isNotBlank() }?.let {
                Text(it, style = MaterialTheme.typography.bodySmall, maxLines = 2)
            }
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically) {
                Text(
                    "${t.priority}${t.dueAtMillis?.let { " · due ${Date(it)}" } ?: ""}",
                    style = MaterialTheme.typography.labelMedium,
                )
                if (!t.isDone) TextButton(onClick = onComplete) { Text("Done") }
            }
        }
    }
}
