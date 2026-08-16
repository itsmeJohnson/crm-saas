package com.crm.mobile.feature.notifications

import androidx.compose.foundation.clickable
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
import androidx.compose.material3.Badge
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
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
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import javax.inject.Inject

@HiltViewModel
class NotificationsViewModel @Inject constructor(
    private val repo: NotificationRepository,
) : ViewModel() {
    private val _loading = MutableStateFlow(true)
    val loading: StateFlow<Boolean> = _loading.asStateFlow()
    private val _offline = MutableStateFlow(false)
    val offline: StateFlow<Boolean> = _offline.asStateFlow()

    val items: StateFlow<List<AppNotification>> = repo.notifications
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())
    val unread: StateFlow<Int> = repo.unreadCount
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), 0)

    init { refresh() }

    fun refresh() {
        _loading.value = true
        viewModelScope.launch { _offline.value = !repo.refresh(); _loading.value = false }
    }

    fun markRead(n: AppNotification) = viewModelScope.launch { repo.markRead(n.id) }
    fun markAllRead() = viewModelScope.launch { repo.markAllRead() }
    fun dismiss(n: AppNotification) = viewModelScope.launch { repo.dismiss(n.id) }
}

@Composable
fun NotificationsScreen(onDeepLink: (String) -> Unit, vm: NotificationsViewModel = hiltViewModel()) {
    val loading by vm.loading.collectAsStateWithLifecycle()
    val offline by vm.offline.collectAsStateWithLifecycle()
    val items by vm.items.collectAsStateWithLifecycle()
    val unread by vm.unread.collectAsStateWithLifecycle()

    Column(Modifier.fillMaxSize().padding(horizontal = 12.dp)) {
        Row(
            Modifier.fillMaxWidth().padding(vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Row(verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Notifications", style = MaterialTheme.typography.titleLarge)
                if (unread > 0) Badge { Text("$unread") }
            }
            TextButton(onClick = vm::markAllRead, enabled = unread > 0) { Text("Mark all read") }
        }
        if (offline) Text(
            "Offline — showing cached notifications", color = MaterialTheme.colorScheme.error,
            style = MaterialTheme.typography.labelMedium, modifier = Modifier.padding(bottom = 8.dp),
        )
        when {
            loading && items.isEmpty() ->
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
            items.isEmpty() ->
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { Text("You're all caught up") }
            else -> LazyColumn(
                verticalArrangement = Arrangement.spacedBy(8.dp),
                contentPadding = PaddingValues(vertical = 4.dp),
            ) {
                items(items, key = { it.id }) { n ->
                    NotificationRow(
                        n,
                        onClick = {
                            if (!n.isRead) vm.markRead(n)
                            deepLinkToRoute(n.linkUrl)?.let(onDeepLink)
                        },
                        onDismiss = { vm.dismiss(n) },
                    )
                }
            }
        }
    }
}

private val TIME_FMT = SimpleDateFormat("EEE d MMM · h:mm a", Locale.getDefault())

@Composable
private fun NotificationRow(n: AppNotification, onClick: () -> Unit, onDismiss: () -> Unit) {
    Card(
        Modifier.fillMaxWidth().clickable(onClick = onClick),
        colors = if (n.isRead) CardDefaults.cardColors()
        else CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
    ) {
        Row(Modifier.padding(14.dp).fillMaxWidth()) {
            Column(Modifier.weight(1f)) {
                Text(
                    n.title,
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = if (n.isRead) FontWeight.Normal else FontWeight.SemiBold,
                    color = if (n.isHigh) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurface,
                )
                n.body.takeIf { it.isNotBlank() }?.let {
                    Text(it, style = MaterialTheme.typography.bodySmall, maxLines = 3)
                }
                val meta = listOf(n.category, TIME_FMT.format(Date(n.createdMillis))).joinToString(" · ")
                Text(meta, style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            TextButton(onClick = onDismiss) { Text("Dismiss") }
        }
    }
}
