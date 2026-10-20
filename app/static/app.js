"use strict";

function prepareCreate() {
    const form = document.getElementById("taskForm");

    if (!form) {
        console.error("Task form not found.");
        return;
    }

    form.action = "/tasks";
    form.reset();

    const modalTitle = document.getElementById("taskModalTitle");
    if (modalTitle) {
        modalTitle.textContent = "Create a task";
    }

    const titleInput = document.getElementById("taskTitle");
    if (titleInput) {
        titleInput.focus();
    }
}

function prepareEdit(id, title, description, priority, tags, dueDate) {
    const form = document.getElementById("taskForm");

    if (!form) {
        console.error("Task form not found.");
        return;
    }

    form.action = `/tasks/${id}/edit`;

    const modalTitle = document.getElementById("taskModalTitle");
    if (modalTitle) {
        modalTitle.textContent = "Edit task";
    }

    const titleInput = document.getElementById("taskTitle");
    const descriptionInput = document.getElementById("taskDescription");
    const priorityInput = document.getElementById("taskPriority");
    const tagsInput = document.getElementById("taskTags");
    const dueDateInput = document.getElementById("taskDueDate");

    if (titleInput) titleInput.value = title || "";
    if (descriptionInput) descriptionInput.value = description || "";
    if (priorityInput) priorityInput.value = priority || "Medium";
    if (tagsInput) tagsInput.value = tags || "";
    if (dueDateInput) dueDateInput.value = dueDate || "";
}


function confirmDelete(id, title) {
    const form = document.getElementById("deleteForm");

    if (!form) {
        console.error("Delete form not found: #deleteForm");
        alert("Unable to delete this task. The delete form was not found.");
        return;
    }

    if (!Number.isInteger(Number(id)) || Number(id) <= 0) {
        console.error("Invalid task ID:", id);
        alert("Invalid task ID.");
        return;
    }

    const taskTitle = String(title || "this task");

    if (!window.confirm(`Delete "${taskTitle}"? This cannot be undone.`)) {
        return;
    }

    // Set the URL that handles task deletion in FastAPI.
    form.method = "post";
    form.action = `/tasks/${Number(id)}/delete`;

    console.log("Submitting delete request:", form.action);

    // Submit the form to FastAPI.
    if (typeof form.requestSubmit === "function") {
        form.requestSubmit();
    } else {
        form.submit();
    }
}


console.log("Todo app.js loaded successfully.");