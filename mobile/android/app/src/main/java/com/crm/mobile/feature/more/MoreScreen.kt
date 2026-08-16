package com.crm.mobile.feature.more

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
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

data class MoreItem(
    val route: String,
    val label: String,
    val description: String,
    val icon: String,
    val managerOnly: Boolean = false,
)

data class MoreCategory(
    val title: String,
    val items: List<MoreItem>,
)

@Composable
fun MoreScreen(onNavigate: (String) -> Unit, vm: MoreViewModel = hiltViewModel()) {
    val role by vm.role.collectAsStateWithLifecycle()
    val isManagerPlus = role in setOf("SuperAdmin", "OrgAdmin", "Manager")

    val categories = listOf(
        MoreCategory(
            title = "Sales & Operations",
            items = listOf(
                MoreItem("leads", "Leads & Enquiries", "Inbound leads, stages & conversion", "🎯"),
                MoreItem("cockpit", "Calling Cockpit", "Click-to-call, disposition & follow-up", "📞"),
                MoreItem("compose", "Quick Communication", "Send WhatsApp, SMS & Email", "💬"),
                MoreItem("reminders", "Follow-up Reminders", "Scheduled call & task reminders", "⏰"),
                MoreItem("tasks", "Tasks & To-Dos", "Team to-dos and milestone tracking", "✅"),
                MoreItem("calendar", "Calendar & Schedule", "Meetings, visits and events", "📅"),
            ),
        ),
        MoreCategory(
            title = "Customer Relations",
            items = listOf(
                MoreItem("customers", "Customers & Accounts", "Directory of active clients", "🏢", managerOnly = true),
                MoreItem("contacts", "Contacts Directory", "Key stakeholder database", "👥", managerOnly = true),
                MoreItem("timeline", "Activity Stream", "Audit log and event history", "📜"),
            ).filter { !it.managerOnly || isManagerPlus },
        ),
        MoreCategory(
            title = "Dental Practice Suite",
            items = listOf(
                MoreItem("dental_dashboard", "Clinic Hub", "Appointments, chair load & dental metrics", "🏥"),
                MoreItem("dental_appointments", "Chairs & Schedules", "Manage chairs, doctors & appointments", "💺"),
                MoreItem("dental_patients", "Patients & Odontogram", "Electronic health records & charting", "🦷"),
                MoreItem("dental_billing", "Treatments & Invoices", "Price master, billing & WhatsApp invoices", "💳"),
                MoreItem("dental_recalls", "Recalls & Retention", "6-month checkups & patient recalls", "🔄"),
            ),
        ),
        MoreCategory(
            title = "Analytics & Reports",
            items = listOf(
                MoreItem("reports", "Performance Reports", "Sales, attendance & team metrics", "📊"),
                MoreItem("notifications", "Notification Center", "In-app alerts and push logs", "🔔"),
            ),
        ),
        MoreCategory(
            title = "Account & System",
            items = listOf(
                MoreItem("profile", "Profile & Settings", "Attendance clock, telephony & biometrics", "⚙️"),
            ),
        ),
    )

    LazyColumn(
        modifier = Modifier.fillMaxSize().padding(horizontal = 14.dp, vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        categories.forEach { category ->
            if (category.items.isNotEmpty()) {
                item(key = "header-${category.title}") {
                    Text(
                        category.title,
                        style = MaterialTheme.typography.labelLarge,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.primary,
                        modifier = Modifier.padding(start = 4.dp, top = 6.dp, bottom = 2.dp),
                    )
                }
                item(key = "card-${category.title}") {
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(16.dp),
                        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
                        border = CardDefaults.outlinedCardBorder().copy(
                            brush = androidx.compose.ui.graphics.SolidColor(MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.6f))
                        )
                    ) {
                        Column {
                            category.items.forEachIndexed { index, item ->
                                Row(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .clickable { onNavigate(item.route) }
                                        .padding(horizontal = 14.dp, vertical = 12.dp),
                                    verticalAlignment = Alignment.CenterVertically,
                                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                                ) {
                                    val (fg, bg) = com.crm.mobile.core.design.DentalColors.getAvatarColor(item.label)
                                    Box(
                                        modifier = Modifier
                                            .size(38.dp)
                                            .clip(RoundedCornerShape(10.dp))
                                            .background(bg),
                                        contentAlignment = Alignment.Center
                                    ) {
                                        Text(item.icon, fontSize = 18.sp)
                                    }
                                    Column(modifier = Modifier.weight(1f)) {
                                        Text(
                                            item.label,
                                            style = MaterialTheme.typography.titleSmall,
                                            fontWeight = FontWeight.Bold,
                                            color = MaterialTheme.colorScheme.onSurface
                                        )
                                        Text(
                                            item.description,
                                            style = MaterialTheme.typography.bodySmall,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                                        )
                                    }
                                    Text(
                                        "›",
                                        style = MaterialTheme.typography.titleLarge,
                                        color = MaterialTheme.colorScheme.outline,
                                        fontWeight = FontWeight.Bold
                                    )
                                }
                                if (index < category.items.size - 1) {
                                    HorizontalDivider(
                                        modifier = Modifier.padding(start = 64.dp, end = 14.dp),
                                        color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.4f)
                                    )
                                }
                            }
                        }
                    }
                }
            }
        }
        item { Box(Modifier.padding(bottom = 20.dp)) {} }
    }
}
