const { io } = require('socket.io-client');
const axios = require('axios');

const socketToken = 'YOUR_SOCKET_API_TOKEN'; // Replace with your token
const ntfyTopic = 'YOUR_NTFY_TOPIC'; // Replace with your ntfy topic

const socket = io(`https://sockets.streamlabs.com?token=${socketToken}`, {
  transports: ['websocket'],
});

socket.on('connect', () => {
  console.log('Connected to Streamlabs Socket.IO');
});

socket.on('event', (data) => {
  if (data.for === 'twitch_account' && data.type === 'chat_message') {
    const message = data.message;
    console.log('New chat message:', message);

    axios.post(`https://ntfy.sh/${ntfyTopic}`, message)
      .then(() => {
        console.log('Message sent to ntfy');
      })
      .catch((err) => {
        console.error('Error sending message to ntfy:', err);
      });
  }
});

socket.on('disconnect', () => {
  console.log('Disconnected from Streamlabs Socket.IO');
});
