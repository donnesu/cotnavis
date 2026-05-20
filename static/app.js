const socket = io();

const languageCommand = document.getElementById("language-command");
const observationTimeline = document.getElementById("observation-timeline");
const plannerQueue = document.getElementById("planner-queue");
const currentCamera = document.getElementById("current-camera");
const currentCameraPlaceholder = document.getElementById("current-camera-placeholder");
const livePill = document.getElementById("live-pill");
const observationMosaicTilesCache = new Map();
const plannerArtifactLeftCropCache = new Map();
let observationRenderVersion = 0;
let latestForesightQueue = [];
let transientIndicator = null;
let lastGoalText = "";
let plannerQueueRenderVersion = 0;
let transientIndicatorCounter = 0;
const revealedPlannerBlockKeys = new Set();
const delayedRevealMsByType = {
  planning: 160,
  replanning: 200,
  executing: 240,
  fix: 320,
};

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

function isObservationMosaicFrame(frame) {
  if (!frame) {
    return false;
  }

  const label = (frame.label || "").toLowerCase();
  const topic = (frame.topic || "").toLowerCase();
  return label.includes("mosaic") || topic.includes("observation_mosaic");
}

function loadImage(src) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("Failed to load observation mosaic image"));
    image.src = src;
  });
}

async function splitMosaicIntoTiles(imageSrc, rows = 2, cols = 2) {
  if (!imageSrc) {
    return [];
  }

  if (observationMosaicTilesCache.has(imageSrc)) {
    return observationMosaicTilesCache.get(imageSrc);
  }

  const image = await loadImage(imageSrc);
  if (image.naturalWidth < cols || image.naturalHeight < rows) {
    observationMosaicTilesCache.set(imageSrc, [imageSrc]);
    return [imageSrc];
  }

  const tileWidth = Math.floor(image.naturalWidth / cols);
  const tileHeight = Math.floor(image.naturalHeight / rows);
  const tiles = [];

  if (tileWidth <= 0 || tileHeight <= 0) {
    observationMosaicTilesCache.set(imageSrc, [imageSrc]);
    return [imageSrc];
  }

  for (let row = 0; row < rows; row += 1) {
    for (let col = 0; col < cols; col += 1) {
      const sx = col * tileWidth;
      const sy = row * tileHeight;
      const sw = col === cols - 1 ? image.naturalWidth - sx : tileWidth;
      const sh = row === rows - 1 ? image.naturalHeight - sy : tileHeight;

      const canvas = document.createElement("canvas");
      canvas.width = sw;
      canvas.height = sh;

      const context = canvas.getContext("2d");
      if (!context) {
        continue;
      }

      context.drawImage(image, sx, sy, sw, sh, 0, 0, sw, sh);
      tiles.push(canvas.toDataURL("image/jpeg", 0.92));
    }
  }

  const result = tiles.length > 0 ? tiles : [imageSrc];
  observationMosaicTilesCache.set(imageSrc, result);
  return result;
}

async function cropPlannerArtifactLeftSide(imageSrc) {
  if (!imageSrc) {
    return imageSrc;
  }

  if (plannerArtifactLeftCropCache.has(imageSrc)) {
    return plannerArtifactLeftCropCache.get(imageSrc);
  }

  let result = imageSrc;
  try {
    const image = await loadImage(imageSrc);
    const cropHeight = image.naturalHeight;
    const cropWidth = Math.floor(image.naturalWidth / 2);
    const isSplitPlanImage = image.naturalWidth >= image.naturalHeight * 1.3;

    if (isSplitPlanImage && cropWidth > 0 && cropHeight > 0) {
      const canvas = document.createElement("canvas");
      canvas.width = cropWidth;
      canvas.height = cropHeight;

      const context = canvas.getContext("2d");
      if (context) {
        context.drawImage(image, 0, 0, cropWidth, cropHeight, 0, 0, cropWidth, cropHeight);
        result = canvas.toDataURL("image/jpeg", 0.92);
      }
    }
  } catch (_error) {
    result = imageSrc;
  }

  plannerArtifactLeftCropCache.set(imageSrc, result);
  return result;
}

async function expandObservationFrames(history) {
  const expandedFrames = [];

  for (const frame of history || []) {
    if (!frame?.image) {
      continue;
    }

    if (!isObservationMosaicFrame(frame)) {
      expandedFrames.push(frame);
      continue;
    }

    try {
      const tiles = await splitMosaicIntoTiles(frame.image, 2, 2);
      tiles.forEach((tileImage, tileIndex) => {
        expandedFrames.push({
          ...frame,
          image: tileImage,
          label: `${frame.label || "observation"} tile ${tileIndex + 1}`,
        });
      });
    } catch (error) {
      expandedFrames.push(frame);
    }
  }

  return expandedFrames;
}

async function renderObservationTimeline(history) {
  const renderVersion = observationRenderVersion + 1;
  observationRenderVersion = renderVersion;

  if (!history || history.length === 0) {
    renderPlaceholder(observationTimeline, "No observation mosaics received");
    return;
  }

  const frames = await expandObservationFrames(history);
  if (renderVersion !== observationRenderVersion) {
    return;
  }

  if (frames.length === 0) {
    renderPlaceholder(observationTimeline, "No observation mosaics received");
    return;
  }

  observationTimeline.classList.remove("empty-state");
  clearElement(observationTimeline);

  frames.forEach((frame, index) => {
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
    label.textContent = index === frames.length - 1 ? "t0" : `t-${frames.length - index - 1}`;

    const indexLabel = document.createElement("div");
    indexLabel.className = "frame-index";
    indexLabel.textContent = frame.label || (index === frames.length - 1 ? "current" : `image ${index + 1}`);

    // meta.appendChild(label);
    // meta.appendChild(indexLabel);
    card.appendChild(imageFrame);
    // card.appendChild(meta);
    observationTimeline.appendChild(card);
  });
}

function blockTitle(block) {
  if (block.type === "planning") {
    return "PLANNING";
  }
  if (block.type === "replanning") {
    return "REPLANNING";
  }
  if (block.type === "executing") {
    return "EXECUTING";
  }
  if (block.type === "accepted") {
    return "ACCEPTED";
  }
  if (block.type === "rejected") {
    return "REJECTED";
  }
  if (block.type === "fix") {
    return "FIX";
  }
  if (block.type === "planned_path") {
    return "PLANNED PATH";
  }
  return (block.type || "UNKNOWN").replaceAll("_", " ").toUpperCase();
}

function blockBodyText(block) {
  if (block.display_text !== null && block.display_text !== undefined) {
    return block.display_text;
  }

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

function shouldUseImageOnlyBody(block) {
  return block.type === "accepted" || block.type === "rejected";
}

function plannerBlockKey(block) {
  const payload = [
    block.type || "unknown",
    block.status || "UNKNOWN",
    block.reflection_id === null || block.reflection_id === undefined ? "n/a" : String(block.reflection_id),
    block.display_text || "",
    block.reason || "",
    block.thinking_text || "",
    block.motion_text || "",
    block.critic_text || "",
    block.path_pose_count === null || block.path_pose_count === undefined ? "" : String(block.path_pose_count),
    block._transient_id || "",
  ];
  return payload.join("|");
}

function delayedRevealMs(block) {
  const type = (block.type || "").toLowerCase();
  return delayedRevealMsByType[type] || 0;
}

function shouldDelayReveal(block) {
  return delayedRevealMs(block) > 0;
}

function renderImageArtifact(block, body, isImageOnlyCard) {
  const artifact = block.motion_image || block.image_plan?.image;
  if (!artifact) {
    return false;
  }

  const image = document.createElement("img");
  image.src = artifact;
  image.alt = blockTitle(block) + " visual artifact";
  image.className = "planned-path-image";
  if (isImageOnlyCard) {
    image.classList.add("planned-path-image-fill");
  }
  body.appendChild(image);

  void cropPlannerArtifactLeftSide(artifact).then((cropped) => {
    if (cropped) {
      image.src = cropped;
    }
  });

  return true;
}

function renderPlannerQueue(queue) {
  if (!queue || queue.length === 0) {
    renderPlaceholder(plannerQueue, "No foresight events received");
    return;
  }

  plannerQueueRenderVersion += 1;
  const renderVersion = plannerQueueRenderVersion;

  plannerQueue.classList.remove("empty-state");
  clearElement(plannerQueue);

  queue.forEach((block) => {
    const connector = document.createElement("div");
    const item = document.createElement("article");
    item.className = `queue-block queue-block-${block.type || "unknown"}`;
    if (block.is_transient) {
      item.classList.add("queue-block-transient");
    }

    const title = document.createElement("div");
    title.className = "queue-title";
    title.textContent = blockTitle(block);

    const status = document.createElement("div");
    status.className = "queue-status";
    const reflection = block.reflection_id === null || block.reflection_id === undefined ? "n/a" : block.reflection_id;
    status.textContent = `reflection ${reflection} / ${block.status || "UNKNOWN"}`;

    const body = document.createElement("div");
    body.className = "queue-body";
    const isImageOnlyCard = shouldUseImageOnlyBody(block);
    if (isImageOnlyCard) {
      body.classList.add("queue-body-image-only");
    }

    if (!block.is_transient && blockTitle(block) !== "FIX") {
      renderImageArtifact(block, body, isImageOnlyCard);
    }

    const bodyText = blockBodyText(block);

    if (!isImageOnlyCard) {
      const text = document.createElement("p");
      text.textContent = bodyText || "No reason text provided.";
      body.appendChild(text);
    }

    item.appendChild(title);
    item.appendChild(status);
    item.appendChild(body);

    const blockKey = plannerBlockKey(block);
    if (shouldDelayReveal(block) && !revealedPlannerBlockKeys.has(blockKey)) {
      const revealDelayMs = delayedRevealMs(block);
      item.classList.add("queue-block-delayed", "queue-block-hidden");
      window.setTimeout(() => {
        if (renderVersion !== plannerQueueRenderVersion || !item.isConnected) {
          return;
        }
        item.classList.remove("queue-block-hidden");
        item.classList.add("queue-block-visible");
      }, revealDelayMs);
      revealedPlannerBlockKeys.add(blockKey);
      if (revealedPlannerBlockKeys.size > 600) {
        revealedPlannerBlockKeys.clear();
      }
    }

    if (plannerQueue.children.length > 0) {
      connector.className = "queue-connector";
      plannerQueue.appendChild(connector);
    }
    plannerQueue.appendChild(item);
  });
}

function normalizeGoalText(value) {
  return (value || "").trim();
}

function createTransientIndicator(type) {
  const indicatorText = {
    planning: "Planner is building a path from the latest command.",
    replanning: "Planner is updating the path after a rejection.",
    executing: "Accepted path is being executed.",
  };

  return {
    type,
    status: type.toUpperCase(),
    display_text: indicatorText[type] || "Planner state update.",
    reflection_id: null,
    is_transient: true,
    _transient_id: `${type}-${Date.now()}-${transientIndicatorCounter += 1}`,
  };
}

function deriveTransientIndicator(queue) {
  for (let index = queue.length - 1; index >= 0; index -= 1) {
    const status = (queue[index]?.status || "").toUpperCase();
    if (status === "REJECTED") {
      return createTransientIndicator("replanning");
    }
    if (status === "ACCEPTED") {
      return createTransientIndicator("executing");
    }
  }
  return null;
}

function renderPlannerQueueWithTransient() {
  const mergedQueue = transientIndicator ? [...latestForesightQueue, transientIndicator] : [...latestForesightQueue];
  renderPlannerQueue(mergedQueue);
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
  const nextGoalText = normalizeGoalText(payload?.text);
  languageCommand.textContent = nextGoalText || "Awaiting command";

  if (nextGoalText && nextGoalText !== lastGoalText) {
    transientIndicator = createTransientIndicator("planning");
    renderPlannerQueueWithTransient();
  }

  lastGoalText = nextGoalText;
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

  void renderObservationTimeline(payload.history || []);
});

socket.on("foresight_trace", (payload) => {
  transientIndicator = null;
  latestForesightQueue = Array.isArray(payload?.queue) ? payload.queue : [];
  transientIndicator = deriveTransientIndicator(latestForesightQueue);
  renderPlannerQueueWithTransient();
});

socket.on("run_context", (payload) => {
  renderRunContext(payload);
});
