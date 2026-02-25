import SwiftUI

struct ContentView: View {
    var body: some View {
        TabView {
            milestoneView(
                title: "Student",
                points: [
                    "Milestone 1: login + role + availability + bookings",
                    "Uses shared KMM networking/repository layer"
                ],
                cardColor: AppTheme.student.opacity(0.15)
            )
            .tabItem { Label("Student", systemImage: "person") }

            milestoneView(
                title: "Teacher",
                points: [
                    "Milestone 2: classes, students, attendance",
                    "Teacher actions map to /api/v1/teacher/*"
                ],
                cardColor: AppTheme.teacherAdmin.opacity(0.15)
            )
            .tabItem { Label("Teacher", systemImage: "person.2") }

            milestoneView(
                title: "Admin",
                points: [
                    "Milestone 3: messages, teachers, venues, users",
                    "Admin actions map to /api/v1/admin/*"
                ],
                cardColor: AppTheme.primary.opacity(0.15)
            )
            .tabItem { Label("Admin", systemImage: "gearshape") }
        }
        .tint(AppTheme.primary)
    }

    private func milestoneView(title: String, points: [String], cardColor: Color) -> some View {
        NavigationStack {
            ZStack {
                AppTheme.background.ignoresSafeArea()
                List(points, id: \.self) { point in
                    Text(point)
                        .foregroundStyle(AppTheme.text)
                        .padding(.vertical, 8)
                        .listRowBackground(cardColor)
                }
                .scrollContentBackground(.hidden)
            }
            .navigationTitle(title)
        }
    }
}
