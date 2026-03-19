const DATASETS = {
  xor: {
    name: "XOR",
    description: "Only one input can be on.",
    samples: [
      { input: [0, 0], target: 0 },
      { input: [0, 1], target: 1 },
      { input: [1, 0], target: 1 },
      { input: [1, 1], target: 0 },
    ],
  },
  and: {
    name: "AND",
    description: "Both inputs must be on.",
    samples: [
      { input: [0, 0], target: 0 },
      { input: [0, 1], target: 0 },
      { input: [1, 0], target: 0 },
      { input: [1, 1], target: 1 },
    ],
  },
  or: {
    name: "OR",
    description: "At least one input must be on.",
    samples: [
      { input: [0, 0], target: 0 },
      { input: [0, 1], target: 1 },
      { input: [1, 0], target: 1 },
      { input: [1, 1], target: 1 },
    ],
  },
};

const state = {
  datasetKey: "xor",
  hiddenSize: 4,
  learningRate: 0.35,
  burstEpochs: 25,
  epoch: 0,
  lossHistory: [],
  isPlaying: false,
  playbackHandle: null,
  network: null,
  predictions: [],
};

const elements = {
  datasetSelect: document.getElementById("dataset-select"),
  hiddenSlider: document.getElementById("hidden-slider"),
  hiddenValue: document.getElementById("hidden-value"),
  rateSlider: document.getElementById("rate-slider"),
  rateValue: document.getElementById("rate-value"),
  batchSlider: document.getElementById("batch-slider"),
  batchValue: document.getElementById("batch-value"),
  stepButton: document.getElementById("step-button"),
  playButton: document.getElementById("play-button"),
  resetButton: document.getElementById("reset-button"),
  datasetPill: document.getElementById("dataset-pill"),
  epochDisplay: document.getElementById("epoch-display"),
  lossDisplay: document.getElementById("loss-display"),
  accuracyDisplay: document.getElementById("accuracy-display"),
  spreadDisplay: document.getElementById("spread-display"),
  statusDisplay: document.getElementById("status-display"),
  architectureLabel: document.getElementById("architecture-label"),
  networkSvg: document.getElementById("network-svg"),
  lossCanvas: document.getElementById("loss-canvas"),
  samplesGrid: document.getElementById("samples-grid"),
};

function sigmoid(value) {
  return 1 / (1 + Math.exp(-value));
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function formatNumber(value, digits = 4) {
  return Number(value).toFixed(digits);
}

class TinyNeuralNetwork {
  constructor(inputSize, hiddenSize, outputSize) {
    this.inputSize = inputSize;
    this.hiddenSize = hiddenSize;
    this.outputSize = outputSize;

    this.weightsIH = Array.from({ length: hiddenSize }, () =>
      Array.from({ length: inputSize }, () => Math.random() * 2 - 1)
    );
    this.biasH = Array.from({ length: hiddenSize }, () => Math.random() * 2 - 1);
    this.weightsHO = Array.from({ length: outputSize }, () =>
      Array.from({ length: hiddenSize }, () => Math.random() * 2 - 1)
    );
    this.biasO = Array.from({ length: outputSize }, () => Math.random() * 2 - 1);
  }

  forward(input) {
    const hidden = this.weightsIH.map((row, hiddenIndex) => {
      const sum = row.reduce(
        (acc, weight, inputIndex) => acc + weight * input[inputIndex],
        this.biasH[hiddenIndex]
      );
      return sigmoid(sum);
    });

    const output = this.weightsHO.map((row, outputIndex) => {
      const sum = row.reduce(
        (acc, weight, hiddenIndex) => acc + weight * hidden[hiddenIndex],
        this.biasO[outputIndex]
      );
      return sigmoid(sum);
    });

    return { input: [...input], hidden, output };
  }

  trainSample(input, target, learningRate) {
    const pass = this.forward(input);
    const output = pass.output[0];
    const error = target - output;
    const outputGradient = error * output * (1 - output);

    const hiddenGradients = pass.hidden.map((hiddenActivation, hiddenIndex) => {
      const downstreamWeight = this.weightsHO[0][hiddenIndex];
      return outputGradient * downstreamWeight * hiddenActivation * (1 - hiddenActivation);
    });

    for (let hiddenIndex = 0; hiddenIndex < this.hiddenSize; hiddenIndex += 1) {
      this.weightsHO[0][hiddenIndex] +=
        learningRate * outputGradient * pass.hidden[hiddenIndex];
    }
    this.biasO[0] += learningRate * outputGradient;

    for (let hiddenIndex = 0; hiddenIndex < this.hiddenSize; hiddenIndex += 1) {
      for (let inputIndex = 0; inputIndex < this.inputSize; inputIndex += 1) {
        this.weightsIH[hiddenIndex][inputIndex] +=
          learningRate * hiddenGradients[hiddenIndex] * input[inputIndex];
      }
      this.biasH[hiddenIndex] += learningRate * hiddenGradients[hiddenIndex];
    }

    return error * error;
  }
}

function getDataset() {
  return DATASETS[state.datasetKey];
}

function createNetwork() {
  state.network = new TinyNeuralNetwork(2, state.hiddenSize, 1);
  state.epoch = 0;
  state.lossHistory = [];
  evaluateNetwork();
}

function evaluateNetwork() {
  const dataset = getDataset();
  state.predictions = dataset.samples.map((sample) => {
    const pass = state.network.forward(sample.input);
    return {
      input: sample.input,
      target: sample.target,
      output: pass.output[0],
      hidden: pass.hidden,
    };
  });

  const loss =
    state.predictions.reduce((sum, prediction) => {
      const diff = prediction.target - prediction.output;
      return sum + diff * diff;
    }, 0) / state.predictions.length;

  if (!state.lossHistory.length || state.lossHistory[state.lossHistory.length - 1] !== loss) {
    state.lossHistory.push(loss);
    if (state.lossHistory.length > 240) {
      state.lossHistory.shift();
    }
  }

  render();
}

function trainEpochs(epochCount) {
  const dataset = getDataset();

  for (let epoch = 0; epoch < epochCount; epoch += 1) {
    let totalLoss = 0;
    for (const sample of dataset.samples) {
      totalLoss += state.network.trainSample(
        sample.input,
        sample.target,
        state.learningRate
      );
    }
    state.epoch += 1;
    state.lossHistory.push(totalLoss / dataset.samples.length);
    if (state.lossHistory.length > 240) {
      state.lossHistory.shift();
    }
  }

  evaluateNetwork();
}

function togglePlayback() {
  state.isPlaying = !state.isPlaying;
  if (state.isPlaying) {
    elements.statusDisplay.textContent = "Auto training";
    elements.playButton.textContent = "Pause";
    state.playbackHandle = window.setInterval(() => {
      trainEpochs(state.burstEpochs);
    }, 180);
  } else {
    stopPlayback();
  }
}

function stopPlayback() {
  state.isPlaying = false;
  elements.statusDisplay.textContent = "Idle";
  elements.playButton.textContent = "Auto Train";
  if (state.playbackHandle) {
    window.clearInterval(state.playbackHandle);
    state.playbackHandle = null;
  }
}

function getAccuracy() {
  const correct = state.predictions.filter((prediction) => {
    const rounded = prediction.output >= 0.5 ? 1 : 0;
    return rounded === prediction.target;
  }).length;

  return (correct / state.predictions.length) * 100;
}

function getPredictionSpread() {
  const outputs = state.predictions.map((prediction) => prediction.output);
  return Math.max(...outputs) - Math.min(...outputs);
}

function getLatestLoss() {
  if (!state.lossHistory.length) {
    return 0;
  }
  return state.lossHistory[state.lossHistory.length - 1];
}

function getWeightColor(weight) {
  const alpha = clamp(Math.abs(weight), 0.08, 1);
  if (weight >= 0) {
    return `rgba(255, 176, 103, ${alpha})`;
  }
  return `rgba(92, 195, 255, ${alpha})`;
}

function buildLayerPositions() {
  const layerX = [150, 460, 770];
  const inputY = [140, 280];
  const hiddenSpacing = state.hiddenSize > 1 ? 220 / (state.hiddenSize - 1) : 0;
  const hiddenY = Array.from({ length: state.hiddenSize }, (_, index) =>
    100 + index * hiddenSpacing
  );
  const outputY = [210];

  return {
    input: inputY.map((y) => ({ x: layerX[0], y })),
    hidden: hiddenY.map((y) => ({ x: layerX[1], y })),
    output: outputY.map((y) => ({ x: layerX[2], y })),
  };
}

function renderNetwork() {
  const dataset = getDataset();
  const focusSample =
    state.predictions.find((prediction) => prediction.target === 1) || state.predictions[0];
  const positions = buildLayerPositions();
  const svgParts = [];

  svgParts.push(
    '<rect x="0" y="0" width="920" height="420" rx="24" fill="rgba(3, 9, 20, 0.28)"></rect>'
  );

  positions.input.forEach((inputNode, inputIndex) => {
    positions.hidden.forEach((hiddenNode, hiddenIndex) => {
      const weight = state.network.weightsIH[hiddenIndex][inputIndex];
      svgParts.push(`
        <line
          x1="${inputNode.x}"
          y1="${inputNode.y}"
          x2="${hiddenNode.x}"
          y2="${hiddenNode.y}"
          stroke="${getWeightColor(weight)}"
          stroke-width="${1.5 + Math.abs(weight) * 2.8}"
          stroke-linecap="round"
        />
      `);
    });
  });

  positions.hidden.forEach((hiddenNode, hiddenIndex) => {
    positions.output.forEach((outputNode, outputIndex) => {
      const weight = state.network.weightsHO[outputIndex][hiddenIndex];
      svgParts.push(`
        <line
          x1="${hiddenNode.x}"
          y1="${hiddenNode.y}"
          x2="${outputNode.x}"
          y2="${outputNode.y}"
          stroke="${getWeightColor(weight)}"
          stroke-width="${1.5 + Math.abs(weight) * 2.8}"
          stroke-linecap="round"
        />
      `);
    });
  });

  const layerDetails = [
    {
      name: "Inputs",
      nodes: positions.input.map((point, index) => ({
        ...point,
        label: `x${index + 1}`,
        value: focusSample.input[index],
      })),
    },
    {
      name: "Hidden",
      nodes: positions.hidden.map((point, index) => ({
        ...point,
        label: `h${index + 1}`,
        value: focusSample.hidden[index],
      })),
    },
    {
      name: "Output",
      nodes: positions.output.map((point, index) => ({
        ...point,
        label: `y${index + 1}`,
        value: focusSample.output,
      })),
    },
  ];

  layerDetails.forEach((layer, layerIndex) => {
    const labelX = [100, 410, 720][layerIndex];
    svgParts.push(
      `<text x="${labelX}" y="52" fill="rgba(237, 244, 255, 0.68)" font-size="16" font-family="Space Grotesk" letter-spacing="2">${layer.name.toUpperCase()}</text>`
    );

    layer.nodes.forEach((node) => {
      const radius = 22 + node.value * 12;
      const fillStrength = 0.22 + node.value * 0.7;
      svgParts.push(`
        <circle
          cx="${node.x}"
          cy="${node.y}"
          r="${radius}"
          fill="rgba(88, 225, 255, ${fillStrength})"
          stroke="rgba(237, 244, 255, 0.92)"
          stroke-width="1.5"
        />
        <text
          x="${node.x}"
          y="${node.y + 5}"
          text-anchor="middle"
          fill="#edf4ff"
          font-size="16"
          font-family="Space Grotesk"
          font-weight="700"
        >${node.label}</text>
        <text
          x="${node.x}"
          y="${node.y + 46}"
          text-anchor="middle"
          fill="rgba(237, 244, 255, 0.72)"
          font-size="13"
          font-family="Space Grotesk"
        >${formatNumber(node.value, 2)}</text>
      `);
    });
  });

  svgParts.push(`
    <text
      x="40"
      y="390"
      fill="rgba(237, 244, 255, 0.68)"
      font-size="14"
      font-family="Space Grotesk"
    >Focused on the positive ${dataset.name} sample so you can see which path lights up.</text>
  `);

  elements.networkSvg.innerHTML = svgParts.join("");
}

function renderLossChart() {
  const ctx = elements.lossCanvas.getContext("2d");
  const { width, height } = elements.lossCanvas;

  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "rgba(4, 10, 19, 0.92)";
  ctx.fillRect(0, 0, width, height);

  ctx.strokeStyle = "rgba(255,255,255,0.08)";
  ctx.lineWidth = 1;
  for (let index = 1; index < 4; index += 1) {
    const y = (height / 4) * index;
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(width, y);
    ctx.stroke();
  }

  if (!state.lossHistory.length) {
    return;
  }

  const maxLoss = Math.max(...state.lossHistory, 0.001);
  const minLoss = Math.min(...state.lossHistory, 0);

  ctx.beginPath();
  state.lossHistory.forEach((loss, index) => {
    const x = (index / Math.max(state.lossHistory.length - 1, 1)) * (width - 40) + 20;
    const normalized = (loss - minLoss) / Math.max(maxLoss - minLoss, 0.0001);
    const y = height - 24 - normalized * (height - 48);
    if (index === 0) {
      ctx.moveTo(x, y);
    } else {
      ctx.lineTo(x, y);
    }
  });
  ctx.strokeStyle = "#58e1ff";
  ctx.lineWidth = 3;
  ctx.stroke();

  ctx.fillStyle = "rgba(237, 244, 255, 0.72)";
  ctx.font = '14px "Space Grotesk"';
  ctx.fillText(`loss: ${formatNumber(getLatestLoss())}`, 20, 24);
  ctx.fillText(`epoch: ${state.epoch}`, width - 110, 24);
}

function renderSamples() {
  const dataset = getDataset();
  elements.samplesGrid.innerHTML = state.predictions
    .map((prediction, index) => {
      const confidence = prediction.output >= 0.5 ? prediction.output : 1 - prediction.output;
      return `
        <article class="sample-card">
          <p class="sample-meta">Sample ${index + 1}</p>
          <p class="sample-input">[${prediction.input.join(", ")}]</p>
          <p class="sample-output">${formatNumber(prediction.output, 3)}</p>
          <p class="sample-target">Target: ${prediction.target}</p>
          <p class="sample-target">Rule: ${dataset.description}</p>
          <p class="sample-target">Confidence: ${Math.round(confidence * 100)}%</p>
        </article>
      `;
    })
    .join("");
}

function renderMetrics() {
  elements.datasetPill.textContent = getDataset().name;
  elements.epochDisplay.textContent = String(state.epoch);
  elements.lossDisplay.textContent = formatNumber(getLatestLoss());
  elements.accuracyDisplay.textContent = `${Math.round(getAccuracy())}%`;
  elements.spreadDisplay.textContent = formatNumber(getPredictionSpread(), 2);
  elements.architectureLabel.textContent = `2 → ${state.hiddenSize} → 1`;
  elements.hiddenValue.textContent = String(state.hiddenSize);
  elements.rateValue.textContent = formatNumber(state.learningRate, 2);
  elements.batchValue.textContent = String(state.burstEpochs);
}

function render() {
  renderMetrics();
  renderNetwork();
  renderLossChart();
  renderSamples();
}

function attachEvents() {
  elements.datasetSelect.addEventListener("change", (event) => {
    state.datasetKey = event.target.value;
    stopPlayback();
    createNetwork();
  });

  elements.hiddenSlider.addEventListener("input", (event) => {
    state.hiddenSize = Number(event.target.value);
    elements.hiddenValue.textContent = String(state.hiddenSize);
  });

  elements.hiddenSlider.addEventListener("change", () => {
    stopPlayback();
    createNetwork();
  });

  elements.rateSlider.addEventListener("input", (event) => {
    state.learningRate = Number(event.target.value);
    elements.rateValue.textContent = formatNumber(state.learningRate, 2);
  });

  elements.batchSlider.addEventListener("input", (event) => {
    state.burstEpochs = Number(event.target.value);
    elements.batchValue.textContent = String(state.burstEpochs);
  });

  elements.stepButton.addEventListener("click", () => {
    stopPlayback();
    elements.statusDisplay.textContent = "Burst training";
    trainEpochs(state.burstEpochs);
    elements.statusDisplay.textContent = "Idle";
  });

  elements.playButton.addEventListener("click", () => {
    togglePlayback();
  });

  elements.resetButton.addEventListener("click", () => {
    stopPlayback();
    createNetwork();
  });
}

attachEvents();
createNetwork();
