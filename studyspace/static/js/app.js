function toggleNavMenu() {
  const btn = document.querySelector('.nav-menu-btn');
  const dropdown = document.getElementById('nav-dropdown');
  btn.classList.toggle('open');
  dropdown.classList.toggle('open');
}

document.addEventListener('click', function(e) {
  const btn = document.querySelector('.nav-menu-btn');
  const dropdown = document.getElementById('nav-dropdown');
  if (btn && dropdown && !btn.contains(e.target)) {
    btn.classList.remove('open');
    dropdown.classList.remove('open');
  }
});

function toggleNavCourses(event) {
  event.stopPropagation();
  const list = document.getElementById('nav-courses-list');
  const toggle = document.getElementById('nav-courses-toggle');
  list.classList.toggle('open');
  toggle.classList.toggle('open');
}

function openModal(id) {
  document.getElementById(id).classList.add("open");
}

function closeModal(id) {
  document.getElementById(id).classList.remove("open");
}

document.addEventListener("keydown", e => {
  if (e.key === "Escape") {
    document.querySelectorAll(".modal-overlay.open").forEach(m => m.classList.remove("open"));
  }
});
