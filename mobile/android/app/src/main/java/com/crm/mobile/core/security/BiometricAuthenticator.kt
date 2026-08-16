package com.crm.mobile.core.security

import androidx.biometric.BiometricManager
import androidx.biometric.BiometricPrompt
import androidx.core.content.ContextCompat
import androidx.fragment.app.FragmentActivity
import kotlin.coroutines.resume
import kotlinx.coroutines.suspendCancellableCoroutine

/**
 * Wraps BiometricPrompt in a suspend call. Used to gate re-entry into the app
 * (and, in production, to unlock the stored refresh token) with fingerprint /
 * face. Falls back to device credential when biometrics aren't enrolled.
 */
class BiometricAuthenticator(private val activity: FragmentActivity) {

    fun canAuthenticate(): Boolean {
        val allowed = BiometricManager.Authenticators.BIOMETRIC_STRONG or
            BiometricManager.Authenticators.DEVICE_CREDENTIAL
        return BiometricManager.from(activity).canAuthenticate(allowed) ==
            BiometricManager.BIOMETRIC_SUCCESS
    }

    suspend fun authenticate(
        title: String = "Unlock CRM",
        subtitle: String = "Confirm it's you",
    ): Boolean = suspendCancellableCoroutine { cont ->
        val executor = ContextCompat.getMainExecutor(activity)
        val prompt = BiometricPrompt(activity, executor,
            object : BiometricPrompt.AuthenticationCallback() {
                override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) {
                    if (cont.isActive) cont.resume(true)
                }
                override fun onAuthenticationError(code: Int, msg: CharSequence) {
                    if (cont.isActive) cont.resume(false)
                }
            })
        val info = BiometricPrompt.PromptInfo.Builder()
            .setTitle(title)
            .setSubtitle(subtitle)
            .setAllowedAuthenticators(
                BiometricManager.Authenticators.BIOMETRIC_STRONG or
                    BiometricManager.Authenticators.DEVICE_CREDENTIAL
            )
            .build()
        prompt.authenticate(info)
    }
}
