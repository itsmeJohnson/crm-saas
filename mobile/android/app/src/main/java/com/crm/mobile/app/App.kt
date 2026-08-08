package com.crm.mobile.app

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import android.os.Bundle
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.fragment.app.FragmentActivity
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.crm.mobile.core.design.CrmTheme
import com.crm.mobile.core.session.SessionManager
import com.crm.mobile.feature.auth.LoginScreen
import com.crm.mobile.feature.dental.DentalRepository
import com.crm.mobile.feature.dental.ui.DentalAppointmentsScreen
import com.crm.mobile.feature.dental.ui.DentalDashboardScreen
import com.crm.mobile.feature.dental.ui.DentalPatientsScreen
import com.crm.mobile.feature.dental.ui.DentalRecallsAnalyticsScreen
import com.crm.mobile.feature.dental.ui.DentalTreatmentsBillingScreen
import com.crm.mobile.feature.notifications.CrmMessagingService
import com.crm.mobile.feature.notifications.deepLinkToRoute
import dagger.hilt.android.AndroidEntryPoint
import dagger.hilt.android.HiltAndroidApp
import javax.inject.Inject

@HiltAndroidApp
class CrmApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        val channel = NotificationChannel(
            CrmMessagingService.CHANNEL_ID,
            "FewClick CRM Dental Alerts",
            NotificationManager.IMPORTANCE_HIGH,
        ).apply { description = "Patient recalls, appointments, and treatment updates" }
        getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
    }
}

object Routes {
    const val LOGIN = "login"
    const val HOME = "home"
    const val DASHBOARD = "dashboard"
    const val APPOINTMENTS = "appointments"
    const val PATIENTS = "patients"
    const val BILLING = "billing"
    const val MORE = "more"
    const val PATIENT_DETAIL = "patient_detail"
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

private data class DentalTab(val route: String, val label: String, val glyph: String)

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
        DentalTab(Routes.DASHBOARD, "Clinic Hub", "🏥"),
        DentalTab(Routes.APPOINTMENTS, "Chairs", "📅"),
        DentalTab(Routes.PATIENTS, "Patients", "🦷"),
        DentalTab(Routes.BILLING, "Billing", "💳"),
        DentalTab(Routes.MORE, "Operations", "⋯"),
    )
    val inner = rememberNavController()
    val backStack by inner.currentBackStackEntryAsState()
    val current = backStack?.destination?.route ?: Routes.DASHBOARD

    LaunchedEffect(initialDeepLink) {
        val route = deepLinkToRoute(initialDeepLink) ?: Routes.MORE.takeIf { initialDeepLink != null }
        route?.let { inner.navigate(it) { launchSingleTop = true } }
    }

    Scaffold(
        bottomBar = {
            NavigationBar {
                tabs.forEach { t ->
                    NavigationBarItem(
                        selected = current.startsWith(t.route),
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
                DentalDashboardScreen(
                    repository = dentalRepository,
                    onNavigateToPatients = { inner.navigate(Routes.PATIENTS) { launchSingleTop = true } },
                    onNavigateToAppointments = { inner.navigate(Routes.APPOINTMENTS) { launchSingleTop = true } },
                    onNavigateToBilling = { inner.navigate(Routes.BILLING) { launchSingleTop = true } },
                    onNavigateToRecalls = { inner.navigate(Routes.MORE) { launchSingleTop = true } },
                    onOpenPatientProfile = { patientId ->
                        inner.navigate("${Routes.PATIENTS}?patientId=$patientId") { launchSingleTop = true }
                    }
                )
            }
            composable(Routes.APPOINTMENTS) {
                DentalAppointmentsScreen(
                    repository = dentalRepository,
                    onOpenPatientProfile = { patientId ->
                        inner.navigate("${Routes.PATIENTS}?patientId=$patientId") { launchSingleTop = true }
                    }
                )
            }
            composable(Routes.PATIENTS) { backStackEntry ->
                val patientId = backStackEntry.arguments?.getString("patientId")
                DentalPatientsScreen(
                    repository = dentalRepository,
                    selectedPatientId = patientId
                )
            }
            composable("${Routes.PATIENTS}?patientId={patientId}") { backStackEntry ->
                val patientId = backStackEntry.arguments?.getString("patientId")
                DentalPatientsScreen(
                    repository = dentalRepository,
                    selectedPatientId = patientId
                )
            }
            composable(Routes.BILLING) {
                DentalTreatmentsBillingScreen(
                    repository = dentalRepository
                )
            }
            composable(Routes.MORE) {
                DentalRecallsAnalyticsScreen(
                    repository = dentalRepository,
                    onLogout = onLoggedOut
                )
            }
        }
    }
}
