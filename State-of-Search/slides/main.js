import Reveal from "reveal.js";
import RevealHighlight from "reveal.js/plugin/highlight";
import RevealNotes from "reveal.js/plugin/notes";

import "reveal.js/reveal.css";
import "reveal.js/plugin/highlight/monokai.css";
import "./theme.css";

const deck = new Reveal({
  hash: true,
  history: true,
  controls: true,
  controlsTutorial: false,
  progress: true,
  center: false,
  width: 1600,
  height: 900,
  margin: 0,
  minScale: 0.2,
  maxScale: 2,
  transition: "fade",
  backgroundTransition: "fade",
  slideNumber: "c/t",
  totalTime: 3000,
  pdfSeparateFragments: false,
  pdfMaxPagesPerSlide: 1,
  plugins: [RevealHighlight, RevealNotes],
});

deck.initialize();
