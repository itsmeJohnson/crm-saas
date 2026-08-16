package com.crm.mobile.app

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import android.os.Bundle
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.activity.compose.BackHandler
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.fragment.app.FragmentActivity
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.crm.mobile.core.design.CrmTheme
import com.crm.mobile.core.design.DentalColors
import com.crm.mobile.core.session.SessionManager
import com.crm.mobile.feature.auth.LoginScreen
import com.crm.mobile.feature.calendar.CalendarScreen
import com.crm.mobile.feature.cockpit.CockpitScreen
import com.crm.mobile.feature.communication.ComposeScreen
import com.crm.mobile.feature.contacts.ContactsListScreen
import com.crm.mobile.feature.customers.CustomersListScreen
import com.crm.mobile.feature.dashboard.DashboardScreen
import com.crm.mobile.feature.dental.DentalRepository
import com.crm.mobile.feature.dental.ui.DentalAppointmentsScreen
import com.crm.mobile.feature.dental.ui.DentalDashboardScreen
import com.crm.mobile.feature.dental.ui.DentalPatientsScreen
import com.crm.mobile.feature.dental.ui.DentalRecallsAnalyticsScreen
import com.crm.mobile.feature.dental.ui.DentalTreatmentsBillingScreen
import com.crm.mobile.feature.leads.LeadsScreen
import com.crm.mobile.feature.more.MoreScreen
import com.crm.mobile.feature.notifications.CrmMessagingService
import com.crm.mobile.feature.notifications.NotificationsScreen
import com.crm.mobile.feature.notifications.deepLinkToRoute
import com.crm.mobile.feature.profile.ProfileScreen
import com.crm.mobile.feature.reminders.ReminderScreen
import com.crm.mobile.feature.reports.ReportsScreen
import com.crm.mobile.feature.tasks.TasksScreen
import com.crm.mobile.feature.timeline.TimelineScreen
import dagger.hilt.android.AndroidEntryPoint
import dagger.hilt.android.HiltAndroidApp
import javax.inject.Inject

@HiltAndroidApp
class CrmApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        val channel = NotificationChannel(
            CrmMessagingService.CHANNEL_ID,
            "FewClick CRM Alerts",
            NotificationManager.IMPORTANCE_HIGH,
        ).apply { description = "CRM lead alerts, reminders, appointments and tasks" }
        getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
    }
}

object Routes {
    const val LOGIN = "login"
    const val HOME = "home"

    // Core CRM
    const val DASHBOARD = "dashboard"
    const val LEADS = "leads"
    const val COCKPIT = "cockpit"
    const val TASKS = "tasks"
    const val CALENDAR = "calendar"
    const val CUSTOMERS = "customers"
    const val CONTACTS = "contacts"
    const val COMPOSE = "compose"
    const val REMINDERS = "reminders"
    const val NOTIFICATIONS = "notifications"
    const val REPORTS = "reports"
    const val PROFILE = "profile"
    const val TIMELINE = "timeline"
    const val MORE = "more"

    // Dental Practice Suite
    const val DENTAL_DASHBOARD = "dental_dashboard"
    const val DENTAL_APPOINTMENTS = "dental_appointments"
    const val DENTAL_PATIENTS = "dental_patients"
    const val DENTAL_BILLING = "dental_billing"
    const val DENTAL_RECALLS = "dental_recalls"
}

@AndroidEntryPoint
class MainActivity : FragmentActivity() {

    @Inject lateinit var session: SessionManager
    @Inject lateinit var dentalRepository: DentalRepository

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            CrmTheme {
                val loggedIn by session.isLoggedIn.collectAsState(initial = null)
                when (loggedIn) {
                    null -> Unit
                    else -> AppNavGraph(
                        startLoggedIn = loggedIn == true,
                        initialDeepLink = intent?.getStringExtra(CrmMessagingService.EXTRA_DEEP_LINK),
                        dentalRepository = dentalRepository
                    )
                }
            }
        }
    }
}

@Composable
fun AppNavGraph(
    startLoggedIn: Boolean,
    initialDeepLink: String? = null,
    dentalRepository: DentalRepository
) {
    val nav = rememberNavController()
    NavHost(
        navController = nav,
        startDestination = if (startLoggedIn) Routes.HOME else Routes.LOGIN,
    ) {
        composable(Routes.LOGIN) {
            LoginScreen(onLoggedIn = {
                dentalRepository.syncWithBackend()
                nav.navigate(Routes.HOME) { popUpTo(Routes.LOGIN) { inclusive = true } }
            })
        }
        composable(Routes.HOME) {
            HomeShell(
                initialDeepLink = initialDeepLink.takeIf { startLoggedIn },
                dentalRepository = dentalRepository,
                onLoggedOut = {
                    nav.navigate(Routes.LOGIN) { popUpTo(Routes.HOME) { inclusive = true } }
                },
            )
        }
    }
}

private data class NavTab(val route: String, val label: String, val glyph: String)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeShell(
    initialDeepLink: String? = null,
    dentalRepository: DentalRepository,
    onLoggedOut: () -> Unit = {}
) {
    LaunchedEffect(Unit) {
        dentalRepository.syncWithBackend()
    }
    val tabs = listOf(
        NavTab(Routes.DASHBOARD, "Dashboard", "📊"),
        NavTab(Routes.LEADS, "Leads", "🎯"),
        NavTab(Routes.COCKPIT, "Calling", "📞"),
        NavTab(Routes.TASKS, "Tasks", "✅"),
        NavTab(Routes.MORE, "More", "⋯"),
    )
    val inner = rememberNavController()
    val backStack by inner.currentBackStackEntryAsState()
    val current = backStack?.destination?.route ?: Routes.DASHBOARD

    LaunchedEffect(initialDeepLink) {
        val route = deepLinkToRoute(initialDeepLink) ?: Routes.MORE.takeIf { initialDeepLink != null }
        route?.let { inner.navigate(it) { launchSingleTop = true } }
    }

    val context = LocalContext.current
    var showExitDialog by remember { mutableStateOf(false) }

    BackHandler(enabled = true) {
        if (current != Routes.DASHBOARD) {
            inner.navigate(Routes.DASHBOARD) {
                popUpTo(Routes.DASHBOARD) { inclusive = true }
            }
        } else {
            showExitDialog = true
        }
    }

    if (showExitDialog) {
        AlertDialog(
            onDismissRequest = { showExitDialog = false },
            title = { Text("Exit Application?", fontWeight = FontWeight.Bold) },
            text = { Text("Are you sure you want to close FewClick CRM?") },
            confirmButton = {
                Button(
                    onClick = {
                        showExitDialog = false
                        (context as? android.app.Activity)?.finish()
                    },
                    colors = ButtonDefaults.buttonColors(
                        containerColor = MaterialTheme.colorScheme.error
                    )
                ) {
                    Text("Exit", fontWeight = FontWeight.Bold)
                }
            },
            dismissButton = {
                OutlinedButton(onClick = { showExitDialog = false }) {
                    Text("Cancel")
                }
            }
        )
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        Box(
                            modifier = Modifier
                                .size(32.dp)
                                .clip(RoundedCornerShape(8.dp))
                                .background(DentalColors.Teal600),
                            contentAlignment = Alignment.Center
                        ) {
                            Text("⚡", fontSize = 16.sp)
                        }
                        Column {
                            Text(
                                "FewClick CRM",
                                style = MaterialTheme.typography.titleMedium,
                                fontWeight = FontWeight.Bold
                            )
                            Text(
                                "Dental & Enterprise Suite",
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    }
                },
                actions = {
                    IconButton(
                        onClick = { inner.navigate(Routes.NOTIFICATIONS) { launchSingleTop = true } }
                    ) {
                        Text("🔔", fontSize = 18.sp)
                    }
                    IconButton(
                        onClick = { inner.navigate(Routes.PROFILE) { launchSingleTop = true } }
                    ) {
                        Text("👤", fontSize = 18.sp)
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface,
                    titleContentColor = MaterialTheme.colorScheme.onSurface
                )
            )
        },
        bottomBar = {
            NavigationBar(
                containerColor = MaterialTheme.colorScheme.surface,
                tonalElevation = 8.dp,
            ) {
                tabs.forEach { t ->
                    val isSelected = current.startsWith(t.route)
                    NavigationBarItem(
                        selected = isSelected,
                        onClick = {
                            inner.navigate(t.route) {
                                popUpTo(inner.graph.startDestinationId) { saveState = true }
                                launchSingleTop = true
                                restoreState = true
                            }
                        },
                        icon = {
                            Box(
                                modifier = Modifier
                                    .padding(2.dp)
                                    .then(
                                        if (isSelected) {
                                            Modifier
                                                .clip(RoundedCornerShape(12.dp))
                                                .background(DentalColors.Teal100)
                                                .padding(horizontal = 14.dp, vertical = 4.dp)
                                        } else Modifier
                                    ),
                                contentAlignment = Alignment.Center
                            ) {
                                Text(t.glyph, fontSize = if (isSelected) 18.sp else 16.sp)
                            }
                        },
                        label = {
                            Text(
                                t.label,
                                style = MaterialTheme.typography.labelSmall,
                                fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal,
                                color = if (isSelected) DentalColors.Teal900 else MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        },
                        colors = NavigationBarItemDefaults.colors(
                            indicatorColor = Color.Transparent,
                        )
                    )
                }
            }
        },
    ) { padding ->
        NavHost(inner, startDestination = Routes.DASHBOARD, modifier = Modifier.padding(padding)) {
            // ---- Core CRM ----
            composable(Routes.DASHBOARD) {
                DashboardScreen(
                    onOpenLeads = { inner.navigate(Routes.LEADS) { launchSingleTop = true } },
                )
            }
            composable(Routes.LEADS) {
                LeadsScreen(
                    onOpenCockpit = { inner.navigate(Routes.COCKPIT) { launchSingleTop = true } },
                    onCompose = { inner.navigate(Routes.COMPOSE) { launchSingleTop = true } },
                )
            }
            composable(Routes.COCKPIT) {
                CockpitScreen()
            }
            composable(Routes.TASKS) {
                TasksScreen()
            }
            composable(Routes.CALENDAR) {
                CalendarScreen()
            }
            composable(Routes.CUSTOMERS) {
                CustomersListScreen(onOpen = {})
            }
            composable(Routes.CONTACTS) {
                ContactsListScreen(onOpen = {})
            }
            composable(Routes.COMPOSE) {
                ComposeScreen(
                    onDone = { inner.popBackStack() },
                )
            }
            composable(Routes.REMINDERS) {
                ReminderScreen(
                    onOpenLead = { inner.navigate(Routes.COCKPIT) },
                )
            }
            composable(Routes.NOTIFICATIONS) {
                NotificationsScreen(
                    onDeepLink = { route -> inner.navigate(route) { launchSingleTop = true } },
                )
            }
            composable(Routes.REPORTS) {
                ReportsScreen()
            }
            composable(Routes.TIMELINE) {
                TimelineScreen()
            }
            composable(Routes.PROFILE) {
                ProfileScreen(onLoggedOut = onLoggedOut)
            }
            composable(Routes.MORE) {
                MoreScreen(
                    onNavigate = { route -> inner.navigate(route) { launchSingleTop = true } },
                )
            }

            // ---- Dental Suite ----
            composable(Routes.DENTAL_DASHBOARD) {
                DentalDashboardScreen(
                    repository = dentalRepository,
                    onNavigateToPatients = { inner.navigate(Routes.DENTAL_PATIENTS) { launchSingleTop = true } },
                    onNavigateToAppointments = { inner.navigate(Routes.DENTAL_APPOINTMENTS) { launchSingleTop = true } },
                    onNavigateToBilling = { inner.navigate(Routes.DENTAL_BILLING) { launchSingleTop = true } },
                    onNavigateToRecalls = { inner.navigate(Routes.DENTAL_RECALLS) { launchSingleTop = true } },
                    onOpenPatientProfile = { patientId ->
                        inner.navigate("${Routes.DENTAL_PATIENTS}?patientId=$patientId") { launchSingleTop = true }
                    }
                )
            }
            composable(Routes.DENTAL_APPOINTMENTS) {
                DentalAppointmentsScreen(
                    repository = dentalRepository,
                    onOpenPatientProfile = { patientId ->
                        inner.navigate("${Routes.DENTAL_PATIENTS}?patientId=$patientId") { launchSingleTop = true }
                    }
                )
            }
            composable(Routes.DENTAL_PATIENTS) { backStackEntry ->
                val patientId = backStackEntry.arguments?.getString("patientId")
                DentalPatientsScreen(
                    repository = dentalRepository,
                    selectedPatientId = patientId
                )
            }
            composable("${Routes.DENTAL_PATIENTS}?patientId={patientId}") { backStackEntry ->
                val patientId = backStackEntry.arguments?.getString("patientId")
                DentalPatientsScreen(
                    repository = dentalRepository,
                    selectedPatientId = patientId
                )
            }
            composable(Routes.DENTAL_BILLING) {
                DentalTreatmentsBillingScreen(
                    repository = dentalRepository
                )
            }
            composable(Routes.DENTAL_RECALLS) {
                DentalRecallsAnalyticsScreen(
                    repository = dentalRepository,
                    onLogout = onLoggedOut
                )
            }
        }
    }
}
