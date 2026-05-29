import React, { useState } from 'react';

import { AccountInfo } from '../../../services/realTradingService';
import { marketDataService } from '../../../services/marketDataService';
import { buildNormalizedHoldings, extractPositionCodes, getPositionSummary } from '../utils/positionMetrics';
import PositionOverview from '../components/PositionOverview';

interface PositionMonitorProps {
    userId: string;
    isActive: boolean;
    accountInfo: AccountInfo | null;
}

const PositionMonitor: React.FC<PositionMonitorProps> = ({ userId: _userId, isActive, accountInfo }) => {
    const [stockNames, setStockNames] = useState<Record<string, string>>({});

    React.useEffect(() => {
        if (!accountInfo || !accountInfo.positions) return;

        const codes = extractPositionCodes(accountInfo).filter(code => !stockNames[code]);
        if (codes.length === 0) return;

        const fetchNames = async () => {
            try {
                const results = await marketDataService.getStockDetailsBatch(codes, 10, 50);
                const newNames: Record<string, string> = {};
                results.forEach(({ code, result }) => {
                    if (result.success && result.data?.name) {
                        newNames[code] = result.data.name;
                    }
                });
                if (Object.keys(newNames).length > 0) {
                    (setStockNames as any)(prev => ({ ...prev, ...newNames }));
                }
            } catch (err) {
                console.error('Failed to fetch stock names in batch:', err);
            }
        };
        fetchNames();
    }, [accountInfo, stockNames]);

    const holdings = React.useMemo(() => {
        return buildNormalizedHoldings(accountInfo, stockNames);
    }, [accountInfo, stockNames]);

    const summary = React.useMemo(() => getPositionSummary(accountInfo), [accountInfo]);

    if (!isActive) return null;

    return (
        <div className="h-full p-2.5 pb-[50px]">
            <PositionOverview holdings={holdings} summary={summary} variant="full" />
        </div>
    );
};

export default PositionMonitor;
