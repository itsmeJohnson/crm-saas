package com.crm.mobile.core.util

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.widget.Toast

object PhoneActions {

    /**
     * Launch the device's native phone dialer with the phone number prepopulated.
     * Works with single/dual SIM without requiring dangerous call permissions.
     */
    fun launchDialer(context: Context, phoneNumber: String?) {
        if (phoneNumber.isNullOrBlank()) {
            Toast.makeText(context, "No phone number available for this contact", Toast.LENGTH_SHORT).show()
            return
        }
        val cleanNumber = phoneNumber.trim()
        val intent = Intent(Intent.ACTION_DIAL).apply {
            data = Uri.parse("tel:${Uri.encode(cleanNumber)}")
            flags = Intent.FLAG_ACTIVITY_NEW_TASK
        }
        try {
            context.startActivity(intent)
        } catch (e: Exception) {
            Toast.makeText(context, "Unable to open phone dialer: ${e.localizedMessage}", Toast.LENGTH_SHORT).show()
        }
    }

    /**
     * Launch WhatsApp to open direct chat with the contact phone number.
     * Falls back to web WhatsApp (wa.me) or standard SMS if WhatsApp is not installed.
     */
    fun launchWhatsApp(context: Context, phoneNumber: String?, message: String? = null) {
        if (phoneNumber.isNullOrBlank()) {
            Toast.makeText(context, "No phone number available for this contact", Toast.LENGTH_SHORT).show()
            return
        }

        // Clean digits and ensure country code format (default India 91 if 10 digits)
        val digitsOnly = phoneNumber.filter { it.isDigit() }
        val formattedNumber = when {
            digitsOnly.length == 10 -> "91$digitsOnly"
            digitsOnly.startsWith("0") && digitsOnly.length == 11 -> "91${digitsOnly.drop(1)}"
            else -> digitsOnly
        }

        val encodedMsg = if (!message.isNullOrBlank()) "&text=${Uri.encode(message)}" else ""
        val waUrl = "https://api.whatsapp.com/send?phone=$formattedNumber$encodedMsg"

        // 1. Try launching official WhatsApp app directly
        val waAppIntent = Intent(Intent.ACTION_VIEW).apply {
            data = Uri.parse(waUrl)
            `package` = "com.whatsapp"
            flags = Intent.FLAG_ACTIVITY_NEW_TASK
        }

        try {
            context.startActivity(waAppIntent)
            return
        } catch (_: Exception) {
            // WhatsApp package not directly launched; try WhatsApp Business
        }

        val waBizIntent = Intent(Intent.ACTION_VIEW).apply {
            data = Uri.parse(waUrl)
            `package` = "com.whatsapp.w4b"
            flags = Intent.FLAG_ACTIVITY_NEW_TASK
        }

        try {
            context.startActivity(waBizIntent)
            return
        } catch (_: Exception) {
            // Neither WhatsApp nor WA Business direct package; open browser wa.me link
        }

        val browserIntent = Intent(Intent.ACTION_VIEW).apply {
            data = Uri.parse("https://wa.me/$formattedNumber${if (!message.isNullOrBlank()) "?text=${Uri.encode(message)}" else ""}")
            flags = Intent.FLAG_ACTIVITY_NEW_TASK
        }

        try {
            context.startActivity(browserIntent)
        } catch (_: Exception) {
            // Final fallback: Standard SMS composer
            val smsIntent = Intent(Intent.ACTION_SENDTO).apply {
                data = Uri.parse("smsto:$formattedNumber")
                if (!message.isNullOrBlank()) putExtra("sms_body", message)
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
            try {
                context.startActivity(smsIntent)
            } catch (smsEx: Exception) {
                Toast.makeText(context, "No WhatsApp or SMS app found", Toast.LENGTH_SHORT).show()
            }
        }
    }
}
