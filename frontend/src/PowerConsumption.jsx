import React, { useState, useEffect } from 'react';
import { Bar, Line, Pie } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';

// Register ChartJS components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend
);

// Real-time Power Consumption Component
function PowerConsumption({ devices }) {
  const [powerHistory, setPowerHistory] = useState({});
  const [totalPower, setTotalPower] = useState(0);

  // Calculate real-time power consumption based on device status
  useEffect(() => {
    // Calculate current power for devices that are ON
    const onDevices = devices.filter(d => d.status);
    const currentPower = onDevices.reduce((sum, device) => sum + device.energy_consumption, 0);
    setTotalPower(currentPower);

    // Build power history for the line chart
    setPowerHistory({
      labels: devices.map(d => d.name),
      datasets: [
        {
          label: 'Current Power Consumption (W)',
          data: devices.map(d => d.status ? d.energy_consumption : 0),
          backgroundColor: devices.map(d => d.status ? 'rgba(34, 197, 94, 0.7)' : 'rgba(107, 114, 128, 0.2)'),
          borderColor: devices.map(d => d.status ? 'rgba(34, 197, 94, 1)' : 'rgba(107, 114, 128, 0.5)'),
          borderWidth: 2,
          borderRadius: 8,
        },
      ],
    });
  }, [devices]);

  // Pie chart data - Active devices power distribution
  const activeDevices = devices.filter(d => d.status);
  const pieData = {
    labels: activeDevices.map(d => d.name),
    datasets: [
      {
        data: activeDevices.map(d => d.energy_consumption),
        backgroundColor: [
          'rgba(59, 130, 246, 0.8)',   // blue
          'rgba(34, 197, 94, 0.8)',    // green
          'rgba(251, 146, 60, 0.8)',   // orange
          'rgba(239, 68, 68, 0.8)',    // red
          'rgba(168, 85, 247, 0.8)',   // purple
        ],
        borderColor: [
          'rgba(59, 130, 246, 1)',
          'rgba(34, 197, 94, 1)',
          'rgba(251, 146, 60, 1)',
          'rgba(239, 68, 68, 1)',
          'rgba(168, 85, 247, 1)',
        ],
        borderWidth: 2,
      },
    ],
  };

  // Bar chart options
  const barOptions = {
    responsive: true,
    maintainAspectRatio: true,
    plugins: {
      legend: {
        display: true,
        position: 'bottom',
        labels: {
          color: '#fff',
          font: { size: 12, weight: 'bold' },
          padding: 15,
        },
      },
      title: {
        display: true,
        text: 'Real-Time Power Consumption by Device',
        color: '#fff',
        font: { size: 16, weight: 'bold' },
        padding: 20,
      },
      tooltip: {
        backgroundColor: 'rgba(0, 0, 0, 0.8)',
        titleColor: '#fff',
        bodyColor: '#fff',
        borderColor: '#3b82f6',
        borderWidth: 1,
        padding: 10,
        callbacks: {
          label: function(context) {
            return context.parsed.y + ' W';
          }
        }
      }
    },
    scales: {
      y: {
        beginAtZero: true,
        max: 3000,
        ticks: {
          color: '#9ca3af',
          font: { size: 11 },
          callback: function(value) {
            return value + ' W';
          }
        },
        grid: {
          color: 'rgba(255, 255, 255, 0.1)',
        },
      },
      x: {
        ticks: {
          color: '#9ca3af',
          font: { size: 11 },
        },
        grid: {
          color: 'rgba(255, 255, 255, 0.05)',
        },
      },
    },
  };

  // Pie chart options
  const pieOptions = {
    responsive: true,
    maintainAspectRatio: true,
    plugins: {
      legend: {
        display: true,
        position: 'right',
        labels: {
          color: '#fff',
          font: { size: 12, weight: 'bold' },
          padding: 15,
        },
      },
      title: {
        display: true,
        text: 'Active Devices Power Distribution',
        color: '#fff',
        font: { size: 16, weight: 'bold' },
        padding: 20,
      },
      tooltip: {
        backgroundColor: 'rgba(0, 0, 0, 0.8)',
        titleColor: '#fff',
        bodyColor: '#fff',
        borderColor: '#3b82f6',
        borderWidth: 1,
        padding: 10,
        callbacks: {
          label: function(context) {
            return context.label + ': ' + context.parsed + ' W';
          }
        }
      }
    },
  };

  return (
    <div className="power-consumption-container">
      {/* Real-Time Power Summary */}
      <div className="power-summary">
        <div className="power-card total-power">
          <div className="power-card-icon">⚡</div>
          <div className="power-card-content">
            <div className="power-label">Total Current Power</div>
            <div className="power-value">{totalPower.toFixed(0)} W</div>
            <div className="power-subtitle">
              {activeDevices.length} device{activeDevices.length !== 1 ? 's' : ''} active
            </div>
          </div>
        </div>

        <div className="power-card daily-estimate">
          <div className="power-card-icon">📊</div>
          <div className="power-card-content">
            <div className="power-label">Daily Estimate</div>
            <div className="power-value">{(totalPower * 24 / 1000).toFixed(2)} kWh</div>
            <div className="power-subtitle">If running continuously</div>
          </div>
        </div>

        <div className="power-card active-count">
          <div className="power-card-icon">🟢</div>
          <div className="power-card-content">
            <div className="power-label">Devices Running</div>
            <div className="power-value">{activeDevices.length}/{devices.length}</div>
            <div className="power-subtitle">Currently active</div>
          </div>
        </div>
      </div>

      {/* Charts */}
      <div className="charts-grid">
        <div className="chart-container bar-chart">
          <Bar data={powerHistory} options={barOptions} />
        </div>

        {activeDevices.length > 0 && (
          <div className="chart-container pie-chart">
            <Pie data={pieData} options={pieOptions} />
          </div>
        )}
      </div>

      {/* Device Details */}
      <div className="power-devices-list">
        <h3>Active Devices Details</h3>
        {activeDevices.length > 0 ? (
          <div className="power-devices-grid">
            {activeDevices.map(device => (
              <div key={device.id} className="power-device-card">
                <div className="power-device-name">{device.name}</div>
                <div className="power-device-type">{device.type}</div>
                <div className="power-device-consumption">{device.energy_consumption}W</div>
                <div className="power-device-percent">
                  {activeDevices.length > 0 ? ((device.energy_consumption / totalPower) * 100).toFixed(1) : 0}% of total
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="no-active-devices">
            <p>No devices are currently running</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default PowerConsumption;
