package com.crm.mobile.feature.more

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.crm.mobile.core.session.SessionManager
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.stateIn
import javax.inject.Inject

@HiltViewModel
class MoreViewModel @Inject constructor(session: SessionManager) : ViewModel() {
    val role: StateFlow<String?> =
        session.role.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), null)
}

private data class MoreItem(val route: String, val label: String, val managerOnly: Boolean = false)

/** Overflow menu for secondary destinations beyond the 5 bottom-nav slots.
 *  Manager-only entries are hidden for other roles, matching backend RBAC. */
@Composable
fun MoreScreen(onNavigate: (String) -> Unit, vm: MoreViewModel = hiltViewModel()) {
    val role by vm.role.collectAsStateWithLifecycle()
    val isManagerPlus = role in setOf("SuperAdmin", "OrgAdmin", "Manager")

    val items = listOf(
        MoreItem("timeline", "Timeline"),
        MoreItem("calendar", "Calendar"),
        MoreItem("customers", "Customers", managerOnly = true),
        MoreItem("contacts", "Contacts", managerOnly = true),
    ).filter { !it.managerOnly || isManagerPlus }

    LazyColumn(Modifier.fillMaxWidth().padding(12.dp)) {
        items(items, key = { it.route }) { m ->
            Card(Modifier.fillMaxWidth().padding(vertical = 6.dp).clickable { onNavigate(m.route) }) {
                Text(m.label, style = MaterialTheme.typography.titleMedium,
                    modifier = Modifier.fillMaxWidth().padding(18.dp))
            }
        }
    }
}
