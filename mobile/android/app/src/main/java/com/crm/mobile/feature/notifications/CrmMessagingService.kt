package com.crm.mobile.feature.notifications

import android.Manifest
import android.app.PendingIntent
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import com.crm.mobile.app.MainActivity
import com.crm.mobile.core.push.PushRegistrar
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import dagger.hilt.android.AndroidEntryPoint
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import javax.inject.Inject
import kotlin.random.Random

/**
 * Receives FCM pushes. On token rotation it re-registers with the backend; on a
 * message it posts a system notification whose tap deep-links into the app. Data
 * payload keys understood: title, body, link_url. Inert until a Firebase project
 * (google-services.json) is configured — see [PushRegistrar].
 */
@AndroidEntryPoint
class CrmMessagingService : FirebaseMessagingService() {

    @Inject lateinit var pushRegistrar: PushRegistrar
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    override fun onNewToken(token: String) {
        scope.launch { runCatching { pushRegistrar.registerToken(token, Build.MODEL) } }
    }

    override fun onMessageReceived(message: RemoteMessage) {
        val n = message.notification
        val title = n?.title ?: message.data["title"] ?: "CRM"
        val body = n?.body ?: message.data["body"].orEmpty()
        val link = message.data["link_url"] ?: message.data["link"]
        showNotification(title, body, link)
    }

    private fun showNotification(title: String, body: String, link: String?) {
        val intent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            link?.let { putExtra(EXTRA_DEEP_LINK, it) }
        }
        val pending = PendingIntent.getActivity(
            this, 0, intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val notification = NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle(title)
            .setContentText(body)
            .setStyle(NotificationCompat.BigTextStyle().bigText(body))
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setAutoCancel(true)
            .setContentIntent(pending)
            .build()

        // POST_NOTIFICATIONS is runtime-gated on Android 13+; skip quietly if denied.
        val allowed = Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU ||
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) ==
            PackageManager.PERMISSION_GRANTED
        if (allowed) {
            NotificationManagerCompat.from(this).notify(Random.nextInt(), notification)
        }
    }

    companion object {
        const val CHANNEL_ID = "crm_default"
        const val EXTRA_DEEP_LINK = "deep_link"
    }
}
