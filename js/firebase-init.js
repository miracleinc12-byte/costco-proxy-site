/* Firebase 공용 초기화 (order.html, board.html, admin.html) */
const firebaseConfig = {
  apiKey: "AIzaSyDSUUtoHiO3WtJ1IOiFfTPqLlCIG-_LfEI",
  authDomain: "costco-proxy.firebaseapp.com",
  projectId: "costco-proxy",
  storageBucket: "costco-proxy.firebasestorage.app",
  messagingSenderId: "145929393279",
  appId: "1:145929393279:web:30f77a53a4f3fcaec79b4a"
};
firebase.initializeApp(firebaseConfig);
const db = firebase.firestore();
