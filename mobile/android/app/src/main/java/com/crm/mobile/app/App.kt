package com.crm.mobile.app

import android.app.Application
import android.os.Bundle
import androidx.activity.compose.setContent
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.fragment.app.FragmentActivity
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.crm.mobile.core.design.CrmTheme
import com.crm.mobile.core.session.SessionManager
import com.crm.mobile.feature.auth.LoginScreen
import com.crm.mobile.feature.leads.LeadsScreen
import dagger.hilt.android.AndroidEntryPoint
import dagger.hilt.android.HiltAndroidApp
import javax.inject.Inject

@HiltAndroidApp
class CrmApplication : Application()

object Routes {
    const val LOGIN = "login"
    const val LEADS = "leads"
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
        startDestination = if (startLoggedIn) Routes.LEADS else Routes.LOGIN,
    ) {
        composable(Routes.LOGIN) {
            LoginScreen(onLoggedIn = {
                nav.navigate(Routes.LEADS) {
                    popUpTo(Routes.LOGIN) { inclusive = true }
                }
            })
        }
        composable(Routes.LEADS) { LeadsScreen() }
    }
}
