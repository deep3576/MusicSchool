package com.musicschool.mobileapp.ui

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import com.musicschool.mobileapp.ui.screens.AdminScreen
import com.musicschool.mobileapp.ui.screens.StudentScreen
import com.musicschool.mobileapp.ui.screens.TeacherScreen
import com.musicschool.mobileapp.ui.theme.MusicSchoolTheme

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MusicSchoolApp() {
    var tab by rememberSaveable { mutableStateOf(0) }
    val tabs = listOf("Student", "Teacher", "Admin")

    MusicSchoolTheme {
        Scaffold(
            modifier = Modifier.fillMaxSize(),
            topBar = { TopAppBar(title = { Text("The Rhythm School") }) },
            bottomBar = {
                NavigationBar {
                    tabs.forEachIndexed { index, title ->
                        NavigationBarItem(
                            selected = tab == index,
                            onClick = { tab = index },
                            icon = { Text(title.take(1)) },
                            label = { Text(title) },
                        )
                    }
                }
            },
        ) { padding ->
            Column(modifier = Modifier.fillMaxSize().padding(padding)) {
                when (tab) {
                    0 -> StudentScreen()
                    1 -> TeacherScreen()
                    else -> AdminScreen()
                }
            }
        }
    }
}
