const form = document.querySelector("#chat-form");
const messageInput = document.querySelector("#message");
const characterCount = document.querySelector("#character-count");
const providerSelect = document.querySelector("#model-select");
const submitButton = document.querySelector("#submit-button");
const resultCard = document.querySelector("#result-card");
const resultState = document.querySelector("#result-state");
const resultEmpty = document.querySelector("#result-empty");
const resultContent = document.querySelector("#result-content");
const answer = document.querySelector("#answer");
const modelUsed = document.querySelector("#model-used strong");
const metrics = document.querySelector("#metrics");

const metricLabels = {
  steps: "Agent 步骤",
  model_calls: "模型调用",
  tool_calls: "工具调用",
  elapsed_ms: "总耗时",
};

function updateCount() {
  characterCount.textContent = `${messageInput.value.length} / 2000`;
}

function setState(label, stateClass) {
  resultState.textContent = label;
  resultState.className = `result-state ${stateClass}`;
}

function providerLabel(providerId) {
  return [...providerSelect.options].find((option) => option.value === providerId)?.textContent
    || providerId;
}

async function loadProviders() {
  try {
    const response = await fetch("/api/providers", { headers: { Accept: "application/json" } });
    const payload = await response.json();
    if (!response.ok || !payload.ok || !Array.isArray(payload.providers)) {
      return;
    }
    const options = payload.providers.map((provider) => {
      const option = document.createElement("option");
      option.value = provider.id;
      option.textContent = `${provider.label} · ${provider.model}${provider.available ? "" : "（未配置）"}`;
      option.disabled = !provider.available;
      return option;
    });
    providerSelect.replaceChildren(...options);
    providerSelect.value = payload.default_provider;
  } catch {
    // Keep the safe built-in options; a configuration error is shown on submit.
  }
}

function showAnswer(text, summary) {
  resultEmpty.hidden = true;
  resultContent.hidden = false;
  answer.classList.remove("error-message");
  answer.textContent = text;
  modelUsed.textContent = providerLabel(summary.provider);
  metrics.replaceChildren();

  Object.entries(metricLabels).forEach(([key, label]) => {
    const item = document.createElement("div");
    const term = document.createElement("dt");
    const value = document.createElement("dd");
    item.className = "metric";
    term.textContent = label;
    value.textContent = key === "elapsed_ms" ? `${summary[key]} ms` : summary[key];
    item.append(term, value);
    metrics.append(item);
  });
}

function showError(message) {
  resultEmpty.hidden = true;
  resultContent.hidden = false;
  answer.classList.add("error-message");
  answer.textContent = message;
  modelUsed.textContent = providerLabel(providerSelect.value);
  metrics.replaceChildren();
}

document.querySelectorAll(".example-chip").forEach((button) => {
  button.addEventListener("click", () => {
    messageInput.value = button.dataset.example;
    updateCount();
    messageInput.focus();
  });
});

messageInput.addEventListener("input", updateCount);

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = messageInput.value.trim();
  if (!message) {
    messageInput.focus();
    return;
  }

  submitButton.disabled = true;
  providerSelect.disabled = true;
  submitButton.querySelector("span:first-child").textContent = "Agent 思考中";
  resultCard.setAttribute("aria-busy", "true");
  resultEmpty.hidden = false;
  resultContent.hidden = true;
  resultEmpty.querySelector("p").textContent = `正在用 ${providerLabel(providerSelect.value)} 检索食材与菜谱…`;
  setState("运行中", "loading");

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, provider: providerSelect.value }),
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) {
      const requestError = new Error(payload.error?.message || "请求失败，请稍后重试");
      requestError.errorType = payload.error?.type;
      throw requestError;
    }
    showAnswer(payload.answer, payload.summary);
    setState(payload.summary.completed ? "已完成" : "未完整结束", "success");
  } catch (error) {
    const message = error instanceof Error ? error.message : "发生未知错误";
    const errorType = error?.errorType ? `（${error.errorType}）` : "";
    showError(`${providerLabel(providerSelect.value)} 请求失败${errorType}：${message}`);
    setState("运行失败", "error");
  } finally {
    submitButton.disabled = false;
    providerSelect.disabled = false;
    submitButton.querySelector("span:first-child").textContent = "再次推荐";
    resultCard.setAttribute("aria-busy", "false");
  }
});

updateCount();
loadProviders();
