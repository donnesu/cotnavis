const socket = io();

const languageCommand = document.getElementById("language-command");
const observationTimeline = document.getElementById("observation-timeline");
const plannerQueue = document.getElementById("planner-queue");
const currentCamera = document.getElementById("current-camera");
const currentCameraPlaceholder = document.getElementById("current-camera-placeholder");
const livePill = document.getElementById("live-pill");

function clearElement(element) {
  while (element.firstChild) {
    element.removeChild(element.firstChild);
  }
}

function renderPlaceholder(container, text) {
  container.classList.add("empty-state");
  clearElement(container);

  const placeholder = document.createElement("div");
  placeholder.className = "placeholder";
  placeholder.textContent = text;
  container.appendChild(placeholder);
}

function formatTime(value) {
  if (!value) {
    return "not received";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function formatBool(value) {
  if (value === true) {
    return "true";
  }
  if (value === false) {
    return "false";
  }
  return "unknown";
}

function renderObservationTimeline(history) {
  if (!history || history.length === 0) {
    renderPlaceholder(observationTimeline, "No camera frames received");
    return;
  }

  observationTimeline.classList.remove("empty-state");
  clearElement(observationTimeline);

  history.forEach((frame, index) => {
    const card = document.createElement("article");
    card.className = "observation-card";

    const imageFrame = document.createElement("div");
    imageFrame.className = "observation-image-frame";

    const image = document.createElement("img");
    image.src = frame.image;
    image.alt = `${frame.label || "Observation"} frame ${index + 1}`;

    imageFrame.appendChild(image);

    const meta = document.createElement("div");
    meta.className = "observation-meta";

    const label = document.createElement("div");
    label.className = "frame-label";
    label.textContent = index === history.length - 1 ? "t0" : `t-${history.length - index - 1}`;

    const indexLabel = document.createElement("div");
    indexLabel.className = "frame-index";
    indexLabel.textContent = frame.label || (index === history.length - 1 ? "current" : `image ${index + 1}`);

    // meta.appendChild(label);
    // meta.appendChild(indexLabel);
    card.appendChild(imageFrame);
    // card.appendChild(meta);
    observationTimeline.appendChild(card);
  });
}

function blockTitle(block) {
  if (block.type === "accepted") {
    return "ACCEPTED";
  }
  if (block.type === "rejected") {
    return "REJECTED";
  }
  if (block.type === "planned_path") {
    return "PLANNED PATH";
  }
  return (block.type || "UNKNOWN").replaceAll("_", " ").toUpperCase();
}

function blockBodyText(block) {
  const lines = [];

  if (block.reason) {
    lines.push(block.reason);
  }
  if (block.thinking_text) {
    lines.push(`Thinking: ${block.thinking_text}`);
  }
  if (block.motion_text) {
    lines.push(`Motion: ${block.motion_text}`);
  }
  if (block.critic_text) {
    lines.push(`Critic: ${block.critic_text}`);
  }
  if (block.path_pose_count !== null && block.path_pose_count !== undefined) {
    lines.push(`path poses: ${block.path_pose_count}`);
  }

  return lines.join("\n");
}

function renderImageArtifact(block, body) {
  const artifact = block.motion_image || block.image_plan?.image;
  if (artifact) {
    const image = document.createElement("img");
    image.src = artifact;
    image.alt = `${blockTitle(block)} visual artifact`;
    image.className = "planned-path-image";
    body.appendChild(image);
  }
}

function renderPlannerQueue(queue) {
  if (!queue || queue.length === 0) {
    renderPlaceholder(plannerQueue, "No foresight events received");
    return;
  }

  plannerQueue.classList.remove("empty-state");
  clearElement(plannerQueue);

  queue.forEach((block) => {
    const connector = document.createElement("div");
    const item = document.createElement("article");
    item.className = `queue-block queue-block-${block.type || "unknown"}`;

    const title = document.createElement("div");
    title.className = "queue-title";
    title.textContent = blockTitle(block);

    const status = document.createElement("div");
    status.className = "queue-status";
    const reflection = block.reflection_id === null || block.reflection_id === undefined ? "n/a" : block.reflection_id;
    status.textContent = `reflection ${reflection} / ${block.status || "UNKNOWN"}`;

    const body = document.createElement("div");
    body.className = "queue-body";

    renderImageArtifact(block, body);

    const text = document.createElement("p");
    text.textContent = blockBodyText(block) || "No reason text provided.";
    body.appendChild(text);

    item.appendChild(title);
    item.appendChild(status);
    item.appendChild(body);

    if (plannerQueue.children.length > 0) {
      connector.className = "queue-connector";
      plannerQueue.appendChild(connector);
    }
    plannerQueue.appendChild(item);
  });
}

function renderRunContext(context) {
  if (!context) {
    return;
  }

  const autonomy = context.autonomy || {};
  const comparison = context.commandComparison || {};
  const trajectory = context.trajectory || {};
  const rollouts = context.rollouts || {};

  const lines = [
    `autonomy ${formatBool(autonomy.enabled)}`,
    `cmd mismatches ${comparison.mismatch || 0}`,
    `trajectory poses ${trajectory.path_pose_count || 0}`,
    `rollout markers ${rollouts.marker_count || 0}`,
  ];

  livePill.textContent = autonomy.enabled === true ? "Live" : autonomy.enabled === false ? "Gated" : "Waiting";
  livePill.classList.toggle("is-gated", autonomy.enabled === false);
}

socket.on("goal_command", (payload) => {
  languageCommand.textContent = payload?.text || "Awaiting command";
});

socket.on("camera_update", (payload) => {
  if (payload.current?.image) {
    currentCamera.src = payload.current.image;
    currentCamera.classList.add("is-visible");
    currentCameraPlaceholder.classList.add("is-hidden");
  } else {
    currentCamera.removeAttribute("src");
    currentCamera.classList.remove("is-visible");
    currentCameraPlaceholder.classList.remove("is-hidden");
  }

  renderObservationTimeline(payload.history || []);
});

socket.on("foresight_trace", (payload) => {
  renderPlannerQueue(payload.queue || []);
});

socket.on("run_context", (payload) => {
  renderRunContext(payload);
});
