// Import necessary libraries
import React from 'react';
import ReactDOM from 'react-dom/client';

// Define a simple functional component
const App = () => {
  return (
    <div className="App">
      <header className="App-header">
        <h1>Hello, World!</h1>
      </header>
    </div>
  );
};

// Render the app to the DOM
ReactDOM.createRoot(document.getElementById('root')).render(<App />);