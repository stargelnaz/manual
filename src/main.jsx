import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.jsx';
import '@fontsource-variable/crimson-pro/wght.css';
import '@fontsource-variable/crimson-pro/wght-italic.css';
import '@fontsource-variable/archivo/wdth.css'; // weight + width axes (condensed headings)
import '@fontsource-variable/archivo/wdth-italic.css';
import './theme.css';
ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
