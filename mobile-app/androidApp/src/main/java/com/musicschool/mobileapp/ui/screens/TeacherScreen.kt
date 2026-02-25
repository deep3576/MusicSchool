package com.musicschool.mobileapp.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

@Composable
fun TeacherScreen() {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.padding(16.dp)) {
        Text("Milestone 2: Teacher Core", style = MaterialTheme.typography.titleLarge)
        TeacherCard("Today's classes", "GET /api/v1/teacher/bookings")
        TeacherCard("Students", "GET/PATCH /api/v1/teacher/students/{id}")
        TeacherCard("Attendance", "POST present/absent actions")
        Button(onClick = {}, modifier = Modifier.fillMaxWidth()) {
            Text("Sync Teacher Data")
        }
    }
}

@Composable
private fun TeacherCard(title: String, subtitle: String) {
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.tertiary.copy(alpha = 0.14f))) {
        Column(Modifier.padding(12.dp)) {
            Text(title, style = MaterialTheme.typography.titleMedium)
            Text(subtitle)
        }
    }
}
