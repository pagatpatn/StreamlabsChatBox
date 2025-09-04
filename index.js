const { io } = require('socket.io-client');
const axios = require('axios');

const socketToken = process.env.SOCKET_TOKEN;
const ntfyTopic = process.env.NTFY_TOPIC;

if (!socketToken || !ntfyTopic) {
    console.error("Error: SOCKET_TOKEN or NTFY_TOPIC not set.");
    process.exit(1);
}

// Connect to Streamlabs Socket.IO
const socket = io(`https://sockets.streamlabs.com?token=${socketToken}`, {
    transports: ['websocket'],
});

socket.on('connect', () => {
    console.log('✅ Connected to Streamlabs Socket.IO');
});

socket.on('event', (data) => {
    // Log everything for debugging
    console.log('📦 Raw event received:', JSON.stringify(data, null, 2));

    // Only handle chat messages
    if (data.type === 'chat_message') {
        const message = data.message;
        console.log('💬 New chat message:', message);

        axios.post(`https://ntfy.sh/${ntfyTopic}`, message)
            .then(() => console.log('✅ Message sent to ntfy'))
            .catch(err => console.error('❌ Error sending to ntfy:', err.message));
    }
});

socket.on('disconnect', () => {
    console.log('⚠ Disconnected from Streamlabs Socket.IO');
});

socket.on('connect_error', (err) => {
    console.error('❌ Connection error:', err.message);
});
