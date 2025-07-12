import React, { useEffect, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { FaTrophy, FaCrown, FaArrowLeft } from 'react-icons/fa';
import './MultiplayerResultsPage.css'; // Создадим этот файл для стилей
import api from '../../utils/axios';

const MultiplayerResultsPage = () => {
    const location = useLocation();
    const navigate = useNavigate();
    const { lobbyId } = useParams();
    const [results, setResults] = useState({});
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchResults = async () => {
            try {
                setLoading(true);
                const response = await api.get(`/api/multiplayer/lobby/${lobbyId}/results`);
                
                if (response.data.status === 'ok') {
                    setResults(response.data.data);
                } else {
                    setError('Failed to fetch game results');
                }
            } catch (err) {
                setError('Error fetching game results');
                console.error(err);
            } finally {
                setLoading(false);
            }
        };

        fetchResults();
    }, [lobbyId]);

    // Сортируем результаты по убыванию очков
    const sortedPlayerIds = Object.keys(results).sort((a, b) => results[b].score - results[a].score);

    if (loading) {
        return <div className="loading-container">Loading results...</div>;
    }

    if (error) {
        return <div className="error-container">{error}</div>;
    }

    return (
        <div className="multiplayer-results-container">
            <div className="results-card">
                <div className="results-header">
                    <FaTrophy className="trophy-icon" />
                    <h1>Игра завершена!</h1>
                    <p>Лобби: {lobbyId}</p>
                </div>

                <div className="results-list">
                    {sortedPlayerIds.map((playerId, index) => {
                        const playerResult = results[playerId];
                        return (
                            <div key={playerId} className={`player-result-row ${index === 0 ? 'winner' : ''}`}>
                                <span className="player-rank">
                                    {index === 0 ? <FaCrown /> : `${index + 1}.`}
                                </span>
                                <span className="player-name">{playerResult.name}</span>
                                <span className="player-score">{playerResult.score} / {playerResult.total}</span>
                            </div>
                        );
                    })}
                </div>

                <div className="results-actions">
                    <button onClick={() => navigate('/dashboard')} className="back-to-dashboard-btn">
                        <FaArrowLeft /> На главную
                    </button>
                </div>
            </div>
        </div>
    );
};

export default MultiplayerResultsPage; 