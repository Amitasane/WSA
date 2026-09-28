// ==============================
// WSA Authentication Script
// ==============================

document.addEventListener("DOMContentLoaded", function () {

    // ==========================
    // LOGIN FORM VALIDATION
    // ==========================

    const loginForm = document.querySelector('form[action="/login"]');

    if (loginForm) {
        loginForm.addEventListener("submit", function (e) {

            const username = loginForm.querySelector('input[name="username"]').value.trim();
            const password = loginForm.querySelector('input[name="password"]').value.trim();

            if (!username || !password) {
                e.preventDefault();
                alert("Please enter both username and password.");
            }
        });
    }


    // ==========================
    // REGISTER FORM VALIDATION
    // ==========================

    const registerForm = document.querySelector('form[action="/register"]');

    if (registerForm) {
        registerForm.addEventListener("submit", function (e) {

            const username = registerForm.querySelector('input[name="username"]').value.trim();
            const email = registerForm.querySelector('input[name="email"]').value.trim();
            const password = registerForm.querySelector('input[name="password"]').value.trim();
            const confirmPassword = registerForm.querySelector('input[name="confirm_password"]').value.trim();

            if (!username || !email || !password || !confirmPassword) {
                e.preventDefault();
                alert("All fields are required.");
                return;
            }

            if (password.length < 6) {
                e.preventDefault();
                alert("Password must be at least 6 characters long.");
                return;
            }

            if (password !== confirmPassword) {
                e.preventDefault();
                alert("Passwords do not match.");
                return;
            }
        });
    }

});