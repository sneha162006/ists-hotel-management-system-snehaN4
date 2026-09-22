var savedTheme = localStorage.getItem("theme");
if (savedTheme === "dark") {
  document.documentElement.setAttribute("data-theme", "dark");
} else {
  document.documentElement.setAttribute("data-theme", "light");
}

document.addEventListener("DOMContentLoaded", function () {

  function updateThemeButtons() {
    var theme = document.documentElement.getAttribute("data-theme");
    var buttons = document.querySelectorAll(".theme-button");
    for (var i = 0; i < buttons.length; i++) {
      if (theme === "dark") {
        buttons[i].textContent = "\u2600 Light";
      } else {
        buttons[i].textContent = "\uD83C\uDF19 Dark";
      }
    }
  }

  var themeButtons = document.querySelectorAll(".theme-button");
  for (var i = 0; i < themeButtons.length; i++) {
    themeButtons[i].addEventListener("click", function () {
      var current = document.documentElement.getAttribute("data-theme");
      var newTheme = (current === "dark") ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", newTheme);
      localStorage.setItem("theme", newTheme);
      updateThemeButtons();
    });
  }
  updateThemeButtons();

  var showButtons = document.querySelectorAll(".show-button");
  for (var j = 0; j < showButtons.length; j++) {
    showButtons[j].addEventListener("click", function () {
      var box = this.parentElement.querySelector("input");
      if (box.type === "password") {
        box.type = "text";
        this.textContent = "Hide";
      } else {
        box.type = "password";
        this.textContent = "Show";
      }
    });
  }

  var registerForm = document.getElementById("register-form");
  if (registerForm) {
    registerForm.addEventListener("submit", function (event) {
      var password = document.getElementById("password").value;
      var confirm = document.getElementById("confirm_password").value;
      if (password.length < 6) {
        alert("Password must be at least 6 characters.");
        event.preventDefault();
      } else if (password !== confirm) {
        alert("Passwords do not match.");
        event.preventDefault();
      }
    });
  }

  var checkIn = document.getElementById("check_in_date");
  var checkOut = document.getElementById("check_out_date");
  if (checkIn && checkOut) {
    checkIn.form.addEventListener("submit", function (event) {
      if (checkOut.value < checkIn.value) {
        alert("Check-out date cannot be before check-in date.");
        event.preventDefault();
      }
    });
  }

  var roomButton = document.getElementById("room-button");
  var roomPanel = document.getElementById("room-panel");
  if (roomButton && roomPanel) {
    var roomInput = document.getElementById("room_number");
    var roomText = document.getElementById("room-button-text");
    var freeRooms = roomPanel.querySelectorAll(".room-chip.free");

    function updateRooms() {
      var picked = [];
      for (var q = 0; q < freeRooms.length; q++) {
        if (freeRooms[q].classList.contains("selected")) {
          picked.push(freeRooms[q].getAttribute("data-room"));
        }
      }
      roomInput.value = picked.join(",");
      if (picked.length === 0) {
        roomText.textContent = "Select one or more rooms";
      } else if (picked.length === 1) {
        roomText.textContent = "Room " + picked[0];
      } else {
        roomText.textContent = "Rooms " + picked.join(", ") + " (" + picked.length + ")";
      }
    }

    roomButton.addEventListener("click", function () {
      roomPanel.classList.toggle("open");
    });

    for (var r = 0; r < freeRooms.length; r++) {
      freeRooms[r].addEventListener("click", function () {
        this.classList.toggle("selected");
        updateRooms();
      });
    }

    document.getElementById("room-clear").addEventListener("click", function () {
      for (var q = 0; q < freeRooms.length; q++) {
        freeRooms[q].classList.remove("selected");
      }
      updateRooms();
    });
    document.getElementById("room-done").addEventListener("click", function () {
      roomPanel.classList.remove("open");
    });

    document.addEventListener("click", function (event) {
      if (!roomButton.parentElement.contains(event.target)) {
        roomPanel.classList.remove("open");
      }
    });

    roomInput.form.addEventListener("submit", function (event) {
      if (roomInput.value === "") {
        alert("Please select at least one room.");
        roomPanel.classList.add("open");
        event.preventDefault();
      }
    });
  }

  setTimeout(function () {
    var messages = document.querySelectorAll(".message");
    for (var k = 0; k < messages.length; k++) {
      messages[k].style.display = "none";
    }
  }, 5000);
});
