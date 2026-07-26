package com.crm.mobile.core.database

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import com.crm.mobile.feature.leads.LeadDao
import com.crm.mobile.feature.leads.LeadEntity
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Database(entities = [LeadEntity::class], version = 1, exportSchema = false)
abstract class AppDatabase : RoomDatabase() {
    abstract fun leadDao(): LeadDao
}

@Module
@InstallIn(SingletonComponent::class)
object DatabaseModule {

    @Provides @Singleton
    fun database(@ApplicationContext ctx: Context): AppDatabase =
        // For production, wrap with SQLCipher (SupportFactory) + a key from the
        // Keystore-backed EncryptedFile so the cache is encrypted at rest.
        Room.databaseBuilder(ctx, AppDatabase::class.java, "crm.db")
            .fallbackToDestructiveMigration()
            .build()

    @Provides
    fun leadDao(db: AppDatabase): LeadDao = db.leadDao()
}
