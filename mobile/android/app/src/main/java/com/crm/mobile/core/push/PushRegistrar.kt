package com.crm.mobile.core.push

import com.crm.mobile.core.session.SessionManager
import com.google.firebase.messaging.FirebaseMessaging
import com.squareup.moshi.JsonClass
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import kotlinx.coroutines.suspendCancellableCoroutine
import retrofit2.http.Body
import retrofit2.http.POST
import javax.inject.Inject
import javax.inject.Singleton
import kotlin.coroutines.resume

// ---- Device-token endpoints (Gap A) ----

@JsonClass(generateAdapter = true)
data class DeviceRegisterReq(val token: String, val platform: String, val device_name: String?)

@JsonClass(generateAdapter = true)
data class DeviceRegisterResp(val id: String, val platform: String)

@JsonClass(generateAdapter = true)
data class DeviceUnregisterReq(val token: String)

interface DeviceApi {
    @POST("notifications/devices")
    suspend fun register(@Body body: DeviceRegisterReq): DeviceRegisterResp

    @POST("notifications/devices/unregister")
    suspend fun unregister(@Body body: DeviceUnregisterReq)
}

/** Abstracts the FCM token fetch so [PushRegistrar] stays unit-testable without
 *  a Firebase runtime. The real provider (below) returns null when Firebase is
 *  not configured, so push simply stays inert until google-services.json is added. */
fun interface FcmTokenProvider {
    suspend fun token(): String?
}

/**
 * Registers this device's native push token with the backend after login and
 * unregisters it on logout. Every path is best-effort: a missing Firebase config
 * or a network error must never block sign-in or sign-out.
 */
@Singleton
class PushRegistrar @Inject constructor(
    private val api: DeviceApi,
    private val session: SessionManager,
    private val tokenProvider: FcmTokenProvider,
) {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    /** Fire-and-forget registration for the current FCM token. Never throws. */
    fun registerAsync(deviceName: String? = null) {
        scope.launch { runCatching { registerNow(deviceName) } }
    }

    /** Fetches the current FCM token and registers it. Returns false if there is
     *  no token (Firebase unconfigured) so callers can no-op silently. */
    suspend fun registerNow(deviceName: String? = null): Boolean {
        val token = tokenProvider.token() ?: return false
        return registerToken(token, deviceName)
    }

    /** Registers an explicit token — used by the messaging service on rotation. */
    suspend fun registerToken(token: String, deviceName: String? = null): Boolean {
        api.register(DeviceRegisterReq(token, PLATFORM_FCM, deviceName))
        session.savePushToken(token)
        return true
    }

    /** Best-effort unregister of the stored token. Call BEFORE clearing the
     *  session, since the token lives in the session store. */
    suspend fun unregisterNow() {
        val token = session.pushToken() ?: return
        runCatching { api.unregister(DeviceUnregisterReq(token)) }
        session.clearPushToken()
    }

    private companion object { const val PLATFORM_FCM = "fcm" }
}

@Module
@InstallIn(SingletonComponent::class)
object PushModule {
    @Provides @Singleton
    fun fcmTokenProvider(): FcmTokenProvider = FcmTokenProvider {
        // Guarded: FirebaseMessaging.getInstance() throws when Firebase is not
        // initialized (no google-services.json) — treat that as "no token".
        runCatching {
            suspendCancellableCoroutine<String?> { cont ->
                FirebaseMessaging.getInstance().token
                    .addOnSuccessListener { cont.resume(it) }
                    .addOnFailureListener { cont.resume(null) }
            }
        }.getOrNull()
    }
}
