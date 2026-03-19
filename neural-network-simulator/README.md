# Neural Network Simulator

This is a small browser-based project that simulates a feed-forward neural network learning simple logic gates.

## Features

- Interactive dataset switching for `XOR`, `AND`, and `OR`
- Adjustable hidden layer size and learning rate
- Manual burst training and automatic continuous training
- Live network diagram showing activations and weights
- Loss chart and prediction cards for each input sample
- A built-in neuroplasticity section connecting network training to human learning

## Run It

Open [index.html](/Users/sumayiarashid/Desktop/Projects/2019/neural-network-simulator/index.html) in a browser.

If you prefer a local server, from this folder you can run:

```bash
python3 -m http.server 8000
```

Then visit `http://127.0.0.1:8000`.

## Notes

- The network is intentionally tiny: `2 -> hidden -> 1`
- Training uses sigmoid activations and basic backpropagation in plain JavaScript
- `XOR` is the most interesting preset because it needs the hidden layer to separate the pattern
- The page includes a short explanation of how repeated feedback-driven learning relates to strengthening the human brain
