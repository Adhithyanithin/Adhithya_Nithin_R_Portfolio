# Emoji Generator from Text using NLP

ML Lab mini project, September 2023. Team: Karnesh E J, Adhithya Nithin R, Adithyan K.

## Pipeline
Text input, preprocessing, emotion detection, emoji mapping, output.

## How it works
- Model: `j-hartmann/emotion-english-distilroberta-base` through the Hugging Face `pipeline`, used pre-trained.
- Emotions: joy, anger, sadness, fear, surprise, love, neutral.
- Any emotion with a score of 0.20 or higher is kept, so mixed feelings give several emoji sets.
- If nothing passes the threshold, the output is neutral.

## Example
`I love spending time with my friends!` gives love (0.75) and joy (0.65).

## Limits
Pre-trained model, hand-written emoji map, no accuracy score reported.

## To add
Notebook file and the report's confusion matrix and charts.
