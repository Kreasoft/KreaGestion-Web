
        document.addEventListener('DOMContentLoaded', function () {
            const form = document.querySelector('.login-form');
            if (form) {
                form.addEventListener('submit', function (e) {
                    const btn = this.querySelector('.login-btn');
                    if (btn) {
                        btn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Accediendo...';
                        btn.disabled = true;
                        btn.style.opacity = '0.8';
                    }
                });
            }

            // Toggle Password Visibility
            const togglePassword = document.querySelector('#togglePassword');
            const password = document.querySelector('input[name="password"]');
            const eyeIcon = document.querySelector('#eyeIcon');

            if (togglePassword && password) {
                togglePassword.addEventListener('click', function () {
                    const type = password.getAttribute('type') === 'password' ? 'text' : 'password';
                    password.setAttribute('type', type);
                    eyeIcon.classList.toggle('fa-eye');
                    eyeIcon.classList.toggle('fa-eye-slash');
                });
            }
        });
    
