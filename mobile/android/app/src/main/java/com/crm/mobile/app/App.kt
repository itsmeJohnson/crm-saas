package com.crm.mobile.app

import android.app.Application
import android.os.Bundle
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.fragment.app.FragmentActivity
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.crm.mobile.core.design.CrmTheme
import com.crm.mobile.core.session.SessionManager
import com.crm.mobile.feature.auth.LoginScreen
import com.crm.mobile.feature.calendar.CalendarScreen
import com.crm.mobile.feature.cockpit.CockpitScreen
import com.crm.mobile.feature.communication.ComposeScreen
import com.crm.mobile.feature.contacts.ContactDetailScreen
import com.crm.mobile.feature.contacts.ContactsListScreen
import com.crm.mobile.feature.customers.CustomerDetailScreen
import com.crm.mobile.feature.customers.CustomersListScreen
import com.crm.mobile.feature.dashboard.DashboardScreen
import com.crm.mobile.feature.leads.LeadsScreen
import com.crm.mobile.feature.more.MoreScreen
import com.crm.mobile.feature.reminders.ReminderScreen
import com.crm.mobile.feature.tasks.TasksScreen
import com.crm.mobile.feature.timeline.TimelineScreen
import dagger.hilt.android.AndroidEntryPoint
import dagger.hilt.android.HiltAndroidApp
import javax.inject.Inject

@HiltAndroidApp
class CrmApplication : Application()

object Routes {
    const val LOGIN = "login"
    const val HOME = "home"
    const val DASHBOARD = "dashboard"
    const val COCKPIT = "cockpit"
    const val LEADS = "leads"
    const val TASKS = "tasks"
    const val MORE = "more"
    const val CALENDAR = "calendar"
    const val CUSTOMERS = "customers"
    const val CONTACTS = "contacts"
    const val TIMELINE = "timeline"
    const val REMINDERS = "reminders"
}

// FragmentActivity so BiometricPrompt can attach.
@AndroidEntryPoint
class MainActivity : FragmentActivity() {

    @Inject lateinit var session: SessionManager

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            CrmTheme {
                val loggedIn by session.isLoggedIn.collectAsState(initial = null)
                when (loggedIn) {
                    null -> Unit // brief splash while the session is read
                    else -> AppNavGraph(startLoggedIn = loggedIn == true)
                }
            }
        }
    }
}

@Composable
fun AppNavGraph(startLoggedIn: Boolean) {
    val nav = rememberNavController()
    NavHost(
        navController = nav,
        startDestination = if (startLoggedIn) Routes.HOME else Routes.LOGIN,
    ) {
        composable(Routes.LOGIN) {
            LoginScreen(onLoggedIn = {
                nav.navigate(Routes.HOME) { popUpTo(Routes.LOGIN) { inclusive = true } }
            })
        }
        composable(Routes.HOME) { HomeShell() }
    }
}

private data class Tab(val route: String, val label: String, val glyph: String)

/** Bottom-nav shell hosting the role's primary destinations. New feature
 *  modules add a Tab + a composable() here — the navigation framework. */
@Composable
fun HomeShell() {
    val tabs = listOf(
        Tab(Routes.DASHBOARD, "Home", "▦"),
        Tab(Routes.COCKPIT, "Dialer", "☎"),
        Tab(Routes.LEADS, "Leads", "☰"),
        Tab(Routes.TASKS, "Tasks", "✔"),
        Tab(Routes.MORE, "More", "⋯"),
    )
    val inner = rememberNavController()
    val backStack by inner.currentBackStackEntryAsState()
    val current = backStack?.destination?.route ?: Routes.DASHBOARD

    Scaffold(
        bottomBar = {
            NavigationBar {
                tabs.forEach { t ->
                    NavigationBarItem(
                        selected = current == t.route,
                        onClick = {
                            inner.navigate(t.route) {
                                popUpTo(inner.graph.startDestinationId) { saveState = true }
                                launchSingleTop = true
                                restoreState = true
                            }
                        },
                        icon = { Text(t.glyph) },
                        label = { Text(t.label) },
                    )
                }
            }
        },
    ) { padding ->
        NavHost(inner, startDestination = Routes.DASHBOARD, modifier = Modifier.padding(padding)) {
            composable(Routes.DASHBOARD) {
                DashboardScreen(onOpenLeads = { inner.navigate(Routes.LEADS) { launchSingleTop = true } })
            }
            composable(Routes.COCKPIT) {
                CockpitScreen(onMessage = { id -> inner.navigate("compose/$id") { launchSingleTop = true } })
            }
            composable("compose/{leadId}") { ComposeScreen(onDone = { inner.popBackStack() }) }
            composable(Routes.LEADS) { LeadsScreen() }
            composable(Routes.TASKS) { TasksScreen() }
            composable(Routes.MORE) { MoreScreen(onNavigate = { r -> inner.navigate(r) { launchSingleTop = true } }) }
            composable(Routes.CALENDAR) { CalendarScreen() }
            composable(Routes.CUSTOMERS) {
                CustomersListScreen(onOpen = { id -> inner.navigate("customer/$id") { launchSingleTop = true } })
            }
            composable("customer/{companyId}") { CustomerDetailScreen() }
            composable(Routes.CONTACTS) {
                ContactsListScreen(onOpen = { id -> inner.navigate("contact/$id") { launchSingleTop = true } })
            }
            composable("contact/{contactId}") { ContactDetailScreen() }
            composable(Routes.TIMELINE) { TimelineScreen() }
            composable(Routes.REMINDERS) {
                ReminderScreen(onOpenLead = { inner.navigate(Routes.LEADS) { launchSingleTop = true } })
            }
        }
    }
}
