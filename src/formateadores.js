const euroFormatter = new Intl.NumberFormat('es-ES', {
    style: 'currency',
    currency: 'EUR',
    minimumFractionDigits: 2,
    maximumFractionDigits: 5
});

const percentFormatter = new Intl.NumberFormat('es-ES', {
    minimumFractionDigits: 1,
    maximumFractionDigits: 2
});

export function formatEuro(value) {
    return euroFormatter.format(Number.isFinite(Number(value)) ? Number(value) : 0);
}

export function formatPercent(value) {
    return `${percentFormatter.format(Number.isFinite(Number(value)) ? Number(value) : 0)} %`;
}

export function formatPages(value) {
    return new Intl.NumberFormat('es-ES').format(
        Number.isFinite(Number(value)) ? Number(value) : 0
    );
}
